from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.core.paginator import Paginator
from decimal import Decimal
import json
import uuid
from datetime import timedelta

from .models import (
    User, GameRound, Bet, Transaction, ChatMessage, 
    Rain, UserStatistics, MpesaPayment, SystemSettings
)
from .utils import generate_reference, process_mpesa_payment


# Authentication Views
def register_view(request):
    """User registration view"""
    if request.method == 'POST':
        data = json.loads(request.body)
        phone_number = data.get('phone_number')
        password = data.get('password')
        full_name = data.get('full_name', '')
        
        # Validate phone number format
        if not phone_number or not password:
            return JsonResponse({
                'success': False,
                'message': 'Phone number and password are required'
            }, status=400)
        
        # Check if user exists
        if User.objects.filter(phone_number=phone_number).exists():
            return JsonResponse({
                'success': False,
                'message': 'Phone number already registered'
            }, status=400)
        
        try:
            # Create user
            user = User.objects.create_user(
                phone_number=phone_number,
                password=password,
                full_name=full_name
            )
            
            # Create user statistics
            UserStatistics.objects.create(user=user)
            
            # Give welcome bonus
            welcome_bonus = Decimal('50.00')
            user.bonus_balance = welcome_bonus
            user.save()
            
            # Record transaction
            Transaction.objects.create(
                user=user,
                transaction_type='bonus',
                amount=welcome_bonus,
                status='completed',
                reference=generate_reference(),
                description='Welcome bonus',
                balance_before=0,
                balance_after=welcome_bonus
            )
            
            login(request, user)
            
            return JsonResponse({
                'success': True,
                'message': 'Registration successful',
                'user': {
                    'phone_number': user.phone_number,
                    'balance': float(user.balance),
                    'bonus_balance': float(user.bonus_balance)
                }
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return render(request, 'register.html')


def login_view(request):
    """User login view"""
    if request.method == 'POST':
        data = json.loads(request.body)
        phone_number = data.get('phone_number')
        password = data.get('password')
        
        user = authenticate(request, phone_number=phone_number, password=password)
        
        if user is not None:
            login(request, user)
            return JsonResponse({
                'success': True,
                'message': 'Login successful',
                'user': {
                    'phone_number': user.phone_number,
                    'balance': float(user.balance),
                    'bonus_balance': float(user.bonus_balance),
                    'total_balance': float(user.get_total_balance())
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid phone number or password'
            }, status=401)
    
    return render(request, 'login.html')


@login_required
def logout_view(request):
    """User logout view"""
    logout(request)
    return redirect('login')


# Main Game Views
@login_required
def home_view(request):
    """Main aviator game view"""
    return render(request, 'home.html')


@login_required
def game_view(request):
    """Aviator game interface"""
    user = request.user
    context = {
        'user': user,
        'balance': user.balance,
        'bonus_balance': user.bonus_balance,
        'total_balance': user.get_total_balance()
    }
    return render(request, 'game.html', context)


# API Endpoints
@login_required
@require_http_methods(["GET"])
def get_user_balance(request):
    """Get current user balance"""
    user = request.user
    return JsonResponse({
        'success': True,
        'balance': float(user.balance),
        'bonus_balance': float(user.bonus_balance),
        'total_balance': float(user.get_total_balance())
    })


@login_required
@require_http_methods(["GET"])
def get_current_round(request):
    """Get current active game round"""
    try:
        current_round = GameRound.objects.filter(
            Q(status='waiting') | Q(status='flying')
        ).first()
        
        if current_round:
            # Get active bets for this round
            active_bets = Bet.objects.filter(
                game_round=current_round,
                status__in=['pending', 'active']
            ).select_related('user').values(
                'user__phone_number', 'amount', 'cashout_multiplier', 
                'status', 'auto_cashout'
            )
            
            return JsonResponse({
                'success': True,
                'round': {
                    'id': str(current_round.id),
                    'round_number': current_round.round_number,
                    'status': current_round.status,
                    'multiplier': float(current_round.multiplier) if current_round.multiplier else 1.00,
                    'start_time': current_round.start_time.isoformat(),
                    'bets': list(active_bets)
                }
            })
        else:
            return JsonResponse({
                'success': True,
                'round': None
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_round_history(request):
    """Get game round history"""
    limit = int(request.GET.get('limit', 50))
    
    rounds = GameRound.objects.filter(
        status='crashed'
    ).order_by('-round_number')[:limit]
    
    history = [{
        'round_number': r.round_number,
        'multiplier': float(r.multiplier) if r.multiplier else 0,
        'end_time': r.end_time.isoformat() if r.end_time else None
    } for r in rounds]
    
    return JsonResponse({
        'success': True,
        'history': history
    })


@login_required
@require_http_methods(["POST"])
def place_bet(request):
    """Place a bet on current round"""
    try:
        data = json.loads(request.body)
        amount = Decimal(str(data.get('amount')))
        auto_cashout = data.get('auto_cashout')
        
        user = request.user
        
        # Validate amount
        if amount < 10:
            return JsonResponse({
                'success': False,
                'message': 'Minimum bet is 10 KES'
            }, status=400)
        
        if amount > 50000:
            return JsonResponse({
                'success': False,
                'message': 'Maximum bet is 50,000 KES'
            }, status=400)
        
        # Check balance
        if user.get_total_balance() < amount:
            return JsonResponse({
                'success': False,
                'message': 'Insufficient balance'
            }, status=400)
        
        # Get current round
        current_round = GameRound.objects.filter(status='waiting').first()
        if not current_round:
            return JsonResponse({
                'success': False,
                'message': 'No active round to place bet'
            }, status=400)
        
        # Check if user already has active bet
        existing_bet = Bet.objects.filter(
            user=user,
            game_round=current_round,
            status__in=['pending', 'active']
        ).exists()
        
        if existing_bet:
            return JsonResponse({
                'success': False,
                'message': 'You already have an active bet on this round'
            }, status=400)
        
        # Deduct from balance
        balance_before = user.get_total_balance()
        if user.bonus_balance >= amount:
            user.bonus_balance -= amount
        elif user.balance >= amount:
            user.balance -= amount
        else:
            # Use both balances
            remaining = amount - user.bonus_balance
            user.bonus_balance = 0
            user.balance -= remaining
        
        user.save()
        
        # Create bet
        bet = Bet.objects.create(
            user=user,
            game_round=current_round,
            amount=amount,
            auto_cashout=Decimal(str(auto_cashout)) if auto_cashout else None,
            status='pending'
        )
        
        # Record transaction
        Transaction.objects.create(
            user=user,
            transaction_type='bet',
            amount=amount,
            status='completed',
            reference=generate_reference(),
            description=f'Bet on round {current_round.round_number}',
            balance_before=balance_before,
            balance_after=user.get_total_balance()
        )
        
        # Update statistics
        stats = user.statistics
        stats.total_bets += 1
        stats.total_wagered += amount
        stats.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Bet placed successfully',
            'bet': {
                'id': str(bet.id),
                'amount': float(bet.amount),
                'auto_cashout': float(bet.auto_cashout) if bet.auto_cashout else None,
                'status': bet.status
            },
            'balance': float(user.balance),
            'bonus_balance': float(user.bonus_balance),
            'total_balance': float(user.get_total_balance())
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def cashout_bet(request):
    """Cashout active bet"""
    try:
        data = json.loads(request.body)
        bet_id = data.get('bet_id')
        current_multiplier = Decimal(str(data.get('multiplier')))
        
        user = request.user
        
        # Get bet
        bet = get_object_or_404(Bet, id=bet_id, user=user, status='active')
        
        # Check if round is still flying
        if bet.game_round.status != 'flying':
            return JsonResponse({
                'success': False,
                'message': 'Round has ended'
            }, status=400)
        
        # Calculate payout
        bet.cashout_multiplier = current_multiplier
        bet.payout = bet.calculate_payout()
        bet.status = 'won'
        bet.save()
        
        # Add to balance
        balance_before = user.get_total_balance()
        user.balance += Decimal(str(bet.payout))
        user.save()
        
        # Record transaction
        Transaction.objects.create(
            user=user,
            transaction_type='win',
            amount=Decimal(str(bet.payout)),
            status='completed',
            reference=generate_reference(),
            description=f'Win from round {bet.game_round.round_number}',
            balance_before=balance_before,
            balance_after=user.get_total_balance()
        )
        
        # Update statistics
        stats = user.statistics
        stats.total_wins += 1
        stats.total_won += Decimal(str(bet.payout))
        if bet.payout > stats.biggest_win:
            stats.biggest_win = bet.payout
        if current_multiplier > stats.biggest_multiplier:
            stats.biggest_multiplier = current_multiplier
        stats.calculate_win_rate()
        stats.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Cashout successful',
            'payout': float(bet.payout),
            'multiplier': float(current_multiplier),
            'balance': float(user.balance),
            'total_balance': float(user.get_total_balance())
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


# Transaction Views
@login_required
def deposit_view(request):
    """Deposit page"""
    return render(request, 'deposit.html')


@login_required
@require_http_methods(["POST"])
def initiate_deposit(request):
    """Initiate M-Pesa deposit"""
    try:
        data = json.loads(request.body)
        amount = Decimal(str(data.get('amount')))
        phone_number = data.get('phone_number', request.user.phone_number)
        
        if amount < 10:
            return JsonResponse({
                'success': False,
                'message': 'Minimum deposit is 10 KES'
            }, status=400)
        
        if amount > 300000:
            return JsonResponse({
                'success': False,
                'message': 'Maximum deposit is 300,000 KES'
            }, status=400)
        
        # Create transaction record
        transaction = Transaction.objects.create(
            user=request.user,
            transaction_type='deposit',
            amount=amount,
            status='pending',
            reference=generate_reference(),
            description=f'M-Pesa deposit',
            balance_before=request.user.get_total_balance(),
            balance_after=request.user.get_total_balance()
        )
        
        # Create M-Pesa payment record
        mpesa_payment = MpesaPayment.objects.create(
            user=request.user,
            transaction=transaction,
            phone_number=phone_number,
            amount=amount,
            status='pending'
        )
        
        # Process M-Pesa STK push (you'll need to implement this)
        result = process_mpesa_payment(phone_number, amount, str(transaction.id))
        
        if result.get('success'):
            mpesa_payment.merchant_request_id = result.get('MerchantRequestID')
            mpesa_payment.checkout_request_id = result.get('CheckoutRequestID')
            mpesa_payment.save()
            
            return JsonResponse({
                'success': True,
                'message': 'STK push sent to your phone',
                'transaction_id': str(transaction.id),
                'checkout_request_id': mpesa_payment.checkout_request_id
            })
        else:
            transaction.status = 'failed'
            transaction.save()
            mpesa_payment.status = 'failed'
            mpesa_payment.result_desc = result.get('message', 'Failed to process payment')
            mpesa_payment.save()
            
            return JsonResponse({
                'success': False,
                'message': result.get('message', 'Failed to initiate payment')
            }, status=400)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def withdraw_funds(request):
    """Withdraw funds to M-Pesa"""
    try:
        data = json.loads(request.body)
        amount = Decimal(str(data.get('amount')))
        phone_number = data.get('phone_number', request.user.phone_number)
        
        user = request.user
        
        if amount < 100:
            return JsonResponse({
                'success': False,
                'message': 'Minimum withdrawal is 100 KES'
            }, status=400)
        
        if amount > user.balance:
            return JsonResponse({
                'success': False,
                'message': 'Insufficient balance'
            }, status=400)
        
        # Deduct from balance
        balance_before = user.get_total_balance()
        user.balance -= amount
        user.save()
        
        # Create transaction
        transaction = Transaction.objects.create(
            user=user,
            transaction_type='withdrawal',
            amount=amount,
            status='pending',
            reference=generate_reference(),
            description='M-Pesa withdrawal',
            balance_before=balance_before,
            balance_after=user.get_total_balance()
        )
        
        # Process withdrawal (implement M-Pesa B2C)
        # For now, mark as completed
        transaction.status = 'completed'
        transaction.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Withdrawal processed successfully',
            'balance': float(user.balance)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
def transaction_history(request):
    """Transaction history page"""
    transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'transactions.html', {'page_obj': page_obj})


@login_required
@require_http_methods(["GET"])
def get_transactions_api(request):
    """Get transactions via API"""
    limit = int(request.GET.get('limit', 20))
    offset = int(request.GET.get('offset', 0))
    
    transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-created_at')[offset:offset+limit]
    
    data = [{
        'id': str(t.id),
        'type': t.transaction_type,
        'amount': float(t.amount),
        'status': t.status,
        'description': t.description,
        'created_at': t.created_at.isoformat()
    } for t in transactions]
    
    return JsonResponse({
        'success': True,
        'transactions': data
    })


# Betting History
@login_required
def betting_history(request):
    """Betting history page"""
    bets = Bet.objects.filter(
        user=request.user
    ).select_related('game_round').order_by('-created_at')
    
    paginator = Paginator(bets, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'betting_history.html', {'page_obj': page_obj})


@login_required
@require_http_methods(["GET"])
def get_betting_history_api(request):
    """Get betting history via API"""
    limit = int(request.GET.get('limit', 20))
    offset = int(request.GET.get('offset', 0))
    
    bets = Bet.objects.filter(
        user=request.user
    ).select_related('game_round').order_by('-created_at')[offset:offset+limit]
    
    data = [{
        'id': str(b.id),
        'round_number': b.game_round.round_number,
        'amount': float(b.amount),
        'multiplier': float(b.cashout_multiplier) if b.cashout_multiplier else None,
        'payout': float(b.payout),
        'status': b.status,
        'created_at': b.created_at.isoformat()
    } for b in bets]
    
    return JsonResponse({
        'success': True,
        'bets': data,
        'has_more': Bet.objects.filter(user=request.user).count() > (offset + limit)
    })


# Chat
@login_required
@require_http_methods(["GET"])
def get_chat_messages(request):
    """Get recent chat messages"""
    limit = int(request.GET.get('limit', 50))
    
    messages = ChatMessage.objects.select_related('user').order_by('-created_at')[:limit]
    messages = reversed(messages)  # Show oldest first
    
    data = [{
        'id': str(m.id),
        'user': m.user.phone_number[-4:] + '****',  # Mask phone number
        'message': m.message,
        'is_system': m.is_system,
        'created_at': m.created_at.isoformat()
    } for m in messages]
    
    return JsonResponse({
        'success': True,
        'messages': data
    })


@login_required
@require_http_methods(["POST"])
def send_chat_message(request):
    """Send chat message"""
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        
        if not message or len(message) > 500:
            return JsonResponse({
                'success': False,
                'message': 'Invalid message'
            }, status=400)
        
        chat_message = ChatMessage.objects.create(
            user=request.user,
            message=message
        )
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': str(chat_message.id),
                'user': request.user.phone_number[-4:] + '****',
                'message': chat_message.message,
                'created_at': chat_message.created_at.isoformat()
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


# Rain
@login_required
@require_http_methods(["GET"])
def get_active_rains(request):
    """Get active rain promotions"""
    rains = Rain.objects.filter(
        status='active',
        end_time__gt=timezone.now()
    ).prefetch_related('participants')
    
    data = [{
        'id': str(r.id),
        'total_amount': float(r.total_amount),
        'amount_per_user': float(r.amount_per_user),
        'participants_count': r.participants.count(),
        'max_participants': r.max_participants,
        'is_full': r.is_full(),
        'end_time': r.end_time.isoformat(),
        'has_joined': request.user in r.participants.all()
    } for r in rains]
    
    return JsonResponse({
        'success': True,
        'rains': data
    })


@login_required
@require_http_methods(["POST"])
def join_rain(request):
    """Join a rain promotion"""
    try:
        data = json.loads(request.body)
        rain_id = data.get('rain_id')
        
        rain = get_object_or_404(Rain, id=rain_id, status='active')
        
        if rain.is_expired():
            return JsonResponse({
                'success': False,
                'message': 'Rain has expired'
            }, status=400)
        
        if rain.is_full():
            return JsonResponse({
                'success': False,
                'message': 'Rain is full'
            }, status=400)
        
        if request.user in rain.participants.all():
            return JsonResponse({
                'success': False,
                'message': 'You have already joined this rain'
            }, status=400)
        
        # Add user to rain
        rain.participants.add(request.user)
        
        # If rain is now full, distribute rewards
        if rain.is_full():
            rain.status = 'completed'
            rain.save()
            
            for participant in rain.participants.all():
                balance_before = participant.get_total_balance()
                participant.bonus_balance += rain.amount_per_user
                participant.save()
                
                Transaction.objects.create(
                    user=participant,
                    transaction_type='rain',
                    amount=rain.amount_per_user,
                    status='completed',
                    reference=generate_reference(),
                    description=f'Rain bonus',
                    balance_before=balance_before,
                    balance_after=participant.get_total_balance()
                )
        
        return JsonResponse({
            'success': True,
            'message': 'Joined rain successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


# Statistics
@login_required
def profile_view(request):
    """User profile and statistics"""
    stats = request.user.statistics
    
    context = {
        'user': request.user,
        'stats': stats
    }
    
    return render(request, 'profile.html', context)


@login_required
@require_http_methods(["GET"])
def get_user_statistics(request):
    """Get user statistics via API"""
    stats = request.user.statistics
    
    return JsonResponse({
        'success': True,
        'statistics': {
            'total_bets': stats.total_bets,
            'total_wins': stats.total_wins,
            'total_wagered': float(stats.total_wagered),
            'total_won': float(stats.total_won),
            'biggest_win': float(stats.biggest_win),
            'biggest_multiplier': float(stats.biggest_multiplier),
            'win_rate': float(stats.win_rate)
        }
    })


# M-Pesa Callback
@csrf_exempt
@require_http_methods(["POST"])
def mpesa_callback(request):
    """M-Pesa payment callback"""
    try:
        data = json.loads(request.body)
        
        # Extract callback data
        body = data.get('Body', {}).get('stkCallback', {})
        merchant_request_id = body.get('MerchantRequestID')
        checkout_request_id = body.get('CheckoutRequestID')
        result_code = body.get('ResultCode')
        result_desc = body.get('ResultDesc')
        
        # Get payment record
        mpesa_payment = MpesaPayment.objects.filter(
            checkout_request_id=checkout_request_id
        ).first()
        
        if not mpesa_payment:
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})
        
        if result_code == 0:  # Success
            # Extract callback metadata
            callback_metadata = body.get('CallbackMetadata', {}).get('Item', [])
            mpesa_receipt = None
            amount = None
            
            for item in callback_metadata:
                if item.get('Name') == 'MpesaReceiptNumber':
                    mpesa_receipt = item.get('Value')
                if item.get('Name') == 'Amount':
                    amount = Decimal(str(item.get('Value')))
            
            # Update payment
            mpesa_payment.result_code = str(result_code)
            mpesa_payment.result_desc = result_desc
            mpesa_payment.mpesa_receipt_number = mpesa_receipt
            mpesa_payment.status = 'success'
            mpesa_payment.save()
            
            # Update transaction
            transaction = mpesa_payment.transaction
            transaction.status = 'completed'
            transaction.mpesa_receipt = mpesa_receipt
            transaction.save()
            
            # Credit user balance
            user = mpesa_payment.user
            user.balance += mpesa_payment.amount
            transaction.balance_after = user.get_total_balance()
            transaction.save()
            user.save()
            
        else:  # Failed
            mpesa_payment.result_code = str(result_code)
            mpesa_payment.result_desc = result_desc
            mpesa_payment.status = 'failed'
            mpesa_payment.save()
            
            transaction = mpesa_payment.transaction
            transaction.status = 'failed'
            transaction.save()
        
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})
        
    except Exception as e:
        return JsonResponse({
            'ResultCode': 1,
            'ResultDesc': str(e)
        })


# Admin views for game management
@login_required
def leaderboard_view(request):
    """Leaderboard page"""
    period = request.GET.get('period', 'all')  # all, today, week, month
    
    if period == 'today':
        start_date = timezone.now().replace(hour=0, minute=0, second=0)
        stats = UserStatistics.objects.filter(
            user__transactions__created_at__gte=start_date,
            user__transactions__transaction_type='win'
        ).annotate(
            period_wins=Sum('user__transactions__amount')
        ).order_by('-period_wins')[:10]
    else:
        stats = UserStatistics.objects.order_by('-total_won')[:10]
    
    return render(request, 'leaderboard.html', {'statistics': stats, 'period': period})