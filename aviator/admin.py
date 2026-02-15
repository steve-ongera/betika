from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, GameRound, Bet, Transaction, ChatMessage,
    Rain, UserStatistics, MpesaPayment, SystemSettings
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('phone_number', 'full_name', 'balance', 'bonus_balance', 'is_active', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'date_joined')
    search_fields = ('phone_number', 'full_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Personal info', {'fields': ('full_name',)}),
        ('Balance', {'fields': ('balance', 'bonus_balance')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ('date_joined', 'last_login')


@admin.register(GameRound)
class GameRoundAdmin(admin.ModelAdmin):
    list_display = ('round_number', 'multiplier', 'status', 'start_time', 'end_time')
    list_filter = ('status', 'start_time')
    search_fields = ('round_number',)
    ordering = ('-round_number',)
    readonly_fields = ('id', 'created_at')


@admin.register(Bet)
class BetAdmin(admin.ModelAdmin):
    list_display = ('user', 'game_round', 'amount', 'cashout_multiplier', 'payout', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__phone_number',)
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'game_round')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'transaction_type', 'amount', 'status', 'reference', 'created_at')
    list_filter = ('transaction_type', 'status', 'created_at')
    search_fields = ('user__phone_number', 'reference', 'mpesa_receipt')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'is_system', 'created_at')
    list_filter = ('is_system', 'created_at')
    search_fields = ('user__phone_number', 'message')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at')


@admin.register(Rain)
class RainAdmin(admin.ModelAdmin):
    list_display = ('total_amount', 'amount_per_user', 'max_participants', 'status', 'start_time', 'end_time')
    list_filter = ('status', 'start_time')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at')
    filter_horizontal = ('participants',)


@admin.register(UserStatistics)
class UserStatisticsAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_bets', 'total_wins', 'total_wagered', 'total_won', 'win_rate', 'biggest_win')
    search_fields = ('user__phone_number',)
    ordering = ('-total_won',)
    readonly_fields = ('updated_at',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(MpesaPayment)
class MpesaPaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'phone_number', 'mpesa_receipt_number', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__phone_number', 'phone_number', 'mpesa_receipt_number', 'checkout_request_id')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'transaction')


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'description', 'updated_at')
    search_fields = ('key', 'description')
    readonly_fields = ('updated_at',)