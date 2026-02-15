from django.urls import path
from . import views

app_name = 'aviator'

urlpatterns = [
    # Authentication
    path('', views.home_view, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Game
    path('game/', views.game_view, name='game'),
    
    # API Endpoints - Game
    path('api/user/balance/', views.get_user_balance, name='api_user_balance'),
    path('api/game/current-round/', views.get_current_round, name='api_current_round'),
    path('api/game/round-history/', views.get_round_history, name='api_round_history'),
    path('api/game/place-bet/', views.place_bet, name='api_place_bet'),
    path('api/game/cashout/', views.cashout_bet, name='api_cashout'),
    
    # Transactions
    path('deposit/', views.deposit_view, name='deposit'),
    path('api/deposit/initiate/', views.initiate_deposit, name='api_initiate_deposit'),
    path('api/withdraw/', views.withdraw_funds, name='api_withdraw'),
    path('transactions/', views.transaction_history, name='transactions'),
    path('api/transactions/', views.get_transactions_api, name='api_transactions'),
    
    # Betting History
    path('betting-history/', views.betting_history, name='betting_history'),
    path('api/betting-history/', views.get_betting_history_api, name='api_betting_history'),
    
    # Chat
    path('api/chat/messages/', views.get_chat_messages, name='api_chat_messages'),
    path('api/chat/send/', views.send_chat_message, name='api_send_message'),
    
    # Rain
    path('api/rain/active/', views.get_active_rains, name='api_active_rains'),
    path('api/rain/join/', views.join_rain, name='api_join_rain'),
    
    # Profile & Statistics
    path('profile/', views.profile_view, name='profile'),
    path('api/statistics/', views.get_user_statistics, name='api_statistics'),
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    
    # M-Pesa Callback
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
]