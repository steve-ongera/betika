from django.urls import path
from . import views, views

app_name = 'aviator'

urlpatterns = [
    # ===================== PUBLIC ROUTES =====================
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
    path('api/deposit/complete/', views.complete_deposit, name='api_complete_deposit'),
    path('api/deposit/status/', views.check_deposit_status, name='api_check_deposit_status'),
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
    
    
    # ===================== ADMIN ROUTES =====================
    # Admin Authentication
    path('admin-login/', views.admin_login_view, name='admin_login'),
    path('admin-logout/', views.admin_logout_view, name='admin_logout'),
    
    # Admin Dashboard
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    # Admin Analytics
    path('admin-analytics/', views.admin_analytics, name='admin_analytics'),
    path('admin-api/analytics-data/', views.get_analytics_data, name='admin_api_analytics'),
    
    # Admin User Management
    path('admin-users/', views.admin_users, name='admin_users'),
    path('admin-users/<uuid:user_id>/', views.admin_user_detail, name='admin_user_detail'),
    path('admin-users/<uuid:user_id>/toggle/', views.admin_toggle_user, name='admin_toggle_user'),
    path('admin-users/<uuid:user_id>/adjust-balance/', views.admin_adjust_balance, name='admin_adjust_balance'),
    
    # Admin Game Management
    path('admin-games/', views.admin_games, name='admin_games'),
    path('admin-games/<uuid:round_id>/', views.admin_game_detail, name='admin_game_detail'),
    path('admin-game-control/', views.admin_game_control, name='admin_game_control'),
    
    # Admin Transactions
    path('admin-transactions/', views.admin_transactions, name='admin_transactions'),
    path('admin-transactions/<uuid:transaction_id>/approve/', views.admin_approve_withdrawal, name='admin_approve_withdrawal'),
    path('admin-transactions/<uuid:transaction_id>/reject/', views.admin_reject_withdrawal, name='admin_reject_withdrawal'),
    
    # Admin Settings
    path('admin-settings/', views.admin_settings, name='admin_settings'),
    
    # Admin Reports
    path('admin-reports/', views.admin_reports, name='admin_reports'),
    path('admin-reports/export/', views.admin_export_report, name='admin_export_report'),
    
    # Admin Live Monitoring
    path('admin-live-monitor/', views.admin_live_monitor, name='admin_live_monitor'),
    path('admin-api/live-stats/', views.get_live_stats, name='admin_api_live_stats'),
]