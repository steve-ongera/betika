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
    return redirect('aviator:login')



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
import json
import uuid
from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction as db_transaction
from .models import (
    User, GameRound, Bet, Transaction, ChatMessage, 
    Rain, UserStatistics, MpesaPayment
)


def generate_reference():
    """Generate unique transaction reference"""
    return f"TXN{uuid.uuid4().hex[:12].upper()}"


def generate_mpesa_receipt():
    """Generate simulated M-Pesa receipt number"""
    return f"QGH{uuid.uuid4().hex[:8].upper()}"


@login_required
def deposit_view(request):
    """Deposit page"""
    return render(request, 'deposit.html')


@login_required
@require_http_methods(["POST"])
def initiate_deposit(request):
    """Initiate M-Pesa deposit (simulated)"""
    try:
        data = json.loads(request.body)
        amount = Decimal(str(data.get('amount', 0)))
        phone_number = data.get('phone_number', request.user.phone_number)
        
        # Validation
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
        
        # Validate phone number format
        if not phone_number or len(phone_number) < 10:
            return JsonResponse({
                'success': False,
                'message': 'Invalid phone number'
            }, status=400)
        
        # Create transaction record with atomic transaction
        with db_transaction.atomic():
            # Lock user row for update
            user = User.objects.select_for_update().get(id=request.user.id)
            
            transaction_ref = generate_reference()
            current_balance = user.get_total_balance()
            
            transaction_record = Transaction.objects.create(
                user=user,
                transaction_type='deposit',
                amount=amount,
                status='pending',
                reference=transaction_ref,
                description=f'M-Pesa deposit of {amount} KES',
                balance_before=current_balance,
                balance_after=current_balance  # Will be updated on completion
            )
            
            # Create M-Pesa payment record (simulated)
            checkout_request_id = f"ws_CO_{uuid.uuid4().hex[:20]}"
            merchant_request_id = f"merchant_{uuid.uuid4().hex[:15]}"
            
            mpesa_payment = MpesaPayment.objects.create(
                user=user,
                transaction=transaction_record,
                phone_number=phone_number,
                amount=amount,
                merchant_request_id=merchant_request_id,
                checkout_request_id=checkout_request_id,
                status='pending'
            )
        
        # Return success response
        return JsonResponse({
            'success': True,
            'message': 'STK push sent to your phone',
            'transaction_id': str(transaction_record.id),
            'checkout_request_id': checkout_request_id,
            'merchant_request_id': merchant_request_id
        })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data'
        }, status=400)
    except Exception as e:
        print(f"Deposit initiation error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Error processing deposit: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def complete_deposit(request):
    """Complete M-Pesa deposit - Actually updates the database balance"""
    try:
        data = json.loads(request.body)
        transaction_id = data.get('transaction_id')
        is_success = data.get('success', True)
        
        if not transaction_id:
            return JsonResponse({
                'success': False,
                'message': 'Transaction ID required'
            }, status=400)
        
        # Use atomic transaction to ensure data consistency
        with db_transaction.atomic():
            # Lock and get transaction record
            transaction_record = Transaction.objects.select_for_update().get(
                id=transaction_id,
                user=request.user
            )
            
            # Prevent double processing
            if transaction_record.status != 'pending':
                return JsonResponse({
                    'success': False,
                    'message': f'Transaction already {transaction_record.status}'
                }, status=400)
            
            # Get M-Pesa payment record
            mpesa_payment = MpesaPayment.objects.select_for_update().get(
                transaction=transaction_record
            )
            
            # Lock user row for update
            user = User.objects.select_for_update().get(id=request.user.id)
            
            if is_success:
                # Generate M-Pesa receipt
                mpesa_receipt = generate_mpesa_receipt()
                
                # Calculate new balance
                old_balance = user.balance
                new_balance = old_balance + transaction_record.amount
                
                # Update user balance - THIS IS THE KEY PART
                user.balance = new_balance
                user.save()
                
                # Update transaction record
                transaction_record.status = 'completed'
                transaction_record.mpesa_receipt = mpesa_receipt
                transaction_record.balance_before = old_balance
                transaction_record.balance_after = new_balance
                transaction_record.save()
                
                # Update M-Pesa payment record
                mpesa_payment.status = 'success'
                mpesa_payment.mpesa_receipt_number = mpesa_receipt
                mpesa_payment.result_code = '0'
                mpesa_payment.result_desc = 'The service request is processed successfully.'
                mpesa_payment.save()
                
                print(f"✅ Deposit completed: User {user.phone_number} | Amount: {transaction_record.amount} | Old Balance: {old_balance} | New Balance: {new_balance}")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Deposit completed successfully',
                    'new_balance': float(user.get_total_balance()),
                    'amount': float(transaction_record.amount),
                    'mpesa_receipt': mpesa_receipt,
                    'old_balance': float(old_balance)
                })
            else:
                # Mark transaction as failed
                transaction_record.status = 'failed'
                transaction_record.save()
                
                # Mark M-Pesa payment as failed
                mpesa_payment.status = 'failed'
                mpesa_payment.result_code = '1'
                mpesa_payment.result_desc = 'Transaction cancelled by user'
                mpesa_payment.save()
                
                print(f"❌ Deposit failed: User {user.phone_number} | Amount: {transaction_record.amount}")
                
                return JsonResponse({
                    'success': False,
                    'message': 'Transaction cancelled or failed'
                }, status=400)
                
    except Transaction.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Transaction not found'
        }, status=404)
    except Exception as e:
        print(f"Complete deposit error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Error completing deposit: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def check_deposit_status(request):
    """Check deposit status"""
    try:
        transaction_id = request.GET.get('transaction_id')
        
        if not transaction_id:
            return JsonResponse({
                'success': False,
                'message': 'Transaction ID required'
            }, status=400)
        
        transaction_record = Transaction.objects.get(
            id=transaction_id,
            user=request.user
        )
        
        mpesa_payment = MpesaPayment.objects.get(
            transaction=transaction_record
        )
        
        return JsonResponse({
            'success': True,
            'status': transaction_record.status,
            'mpesa_status': mpesa_payment.status,
            'amount': float(transaction_record.amount),
            'mpesa_receipt': transaction_record.mpesa_receipt or '',
            'balance_before': float(transaction_record.balance_before),
            'balance_after': float(transaction_record.balance_after)
        })
        
    except Transaction.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Transaction not found'
        }, status=404)
    except Exception as e:
        print(f"Check status error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def user_balance(request):
    """Get user's current balance"""
    try:
        # Refresh user from database to get latest balance
        user = User.objects.get(id=request.user.id)
        
        return JsonResponse({
            'success': True,
            'balance': float(user.balance),
            'bonus_balance': float(user.bonus_balance),
            'total_balance': float(user.get_total_balance())
        })
    except Exception as e:
        print(f"Balance fetch error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
def transactions_view(request):
    """View transaction history"""
    transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-created_at')[:50]
    
    return render(request, 'transactions.html', {
        'transactions': transactions
    })


# Helper function for M-Pesa processing (for future real integration)
def process_mpesa_payment(phone_number, amount, transaction_id):
    """
    Simulated M-Pesa payment processing
    In production, this would make actual API calls to M-Pesa Daraja API
    
    Real implementation would:
    1. Get access token from M-Pesa
    2. Make STK Push request
    3. Return CheckoutRequestID
    4. Handle callback from M-Pesa
    """
    # For now, return simulated success
    return {
        'success': True,
        'MerchantRequestID': f"merchant_{uuid.uuid4().hex[:15]}",
        'CheckoutRequestID': f"ws_CO_{uuid.uuid4().hex[:20]}",
        'ResponseCode': '0',
        'ResponseDescription': 'Success. Request accepted for processing',
        'CustomerMessage': 'Success. Request accepted for processing'
    }
    
    
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