from django.contrib import admin
from django.utils.html import format_html
from django.db import models
from .models import MembershipApplication, Payment, Claim, Share, ContactMessage, UserProfile, ShareDeduction, Notification, Meeting, Announcement, Message

@admin.register(MembershipApplication)
class MembershipApplicationAdmin(admin.ModelAdmin):
    list_display = ['user', 'first_name', 'last_name', 'application_type', 'status', 'created_at']
    list_filter = ['application_type', 'status', 'created_at']
    search_fields = ['first_name', 'last_name', 'email', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Application Info', {
            'fields': ('user', 'application_type', 'status', 'admin_notes')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'middle_name', 'last_name', 'email', 'address', 'phone_main', 'minnesota_id')
        }),
        ('Family Information', {
            'fields': ('spouse', 'spouse_phone', 'authorized_rep')
        }),
        ('Children', {
            'fields': ('child_1', 'child_2', 'child_3', 'child_4', 'child_5')
        }),
        ('Parents & Siblings', {
            'fields': ('parent_1', 'parent_2', 'sibling_1', 'sibling_2')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def minnesota_id_preview(self, obj):
        if obj.minnesota_id:
            return format_html('<a href="{}" target="_blank">View Document</a>', obj.minnesota_id.url)
        return "No document"
    minnesota_id_preview.short_description = "ID Document"

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'payment_type', 'amount', 'payment_method', 'status', 'created_at']
    list_filter = ['payment_type', 'payment_method', 'status', 'created_at']
    search_fields = ['user__username', 'transaction_id']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Payment Info', {
            'fields': ('user', 'payment_type', 'amount', 'payment_method', 'transaction_id')
        }),
        ('Details', {
            'fields': ('description', 'payment_proof')
        }),
        ('Admin', {
            'fields': ('status', 'admin_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def payment_proof_preview(self, obj):
        if obj.payment_proof:
            return format_html('<a href="{}" target="_blank">View Proof</a>', obj.payment_proof.url)
        return "No proof"
    payment_proof_preview.short_description = "Payment Proof"

@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ['user', 'claim_type', 'member_name', 'amount_requested', 'status', 'created_at']
    list_filter = ['claim_type', 'relationship', 'status', 'created_at']
    search_fields = ['user__username', 'member_name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Claim Info', {
            'fields': ('user', 'claim_type', 'member_name', 'relationship', 'incident_date')
        }),
        ('Details', {
            'fields': ('amount_requested', 'description', 'supporting_documents')
        }),
        ('Admin', {
            'fields': ('status', 'admin_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def supporting_docs_preview(self, obj):
        if obj.supporting_documents:
            return format_html('<a href="{}" target="_blank">View Documents</a>', obj.supporting_documents.url)
        return "No documents"
    supporting_docs_preview.short_description = "Supporting Documents"

@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = ['user', 'shares_purchased', 'amount', 'payment_method', 'status', 'created_at']
    list_filter = ['payment_method', 'status', 'created_at']
    search_fields = ['user__username', 'transaction_id']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['approve_shares', 'reject_shares']
    
    def approve_shares(self, request, queryset):
        for share in queryset:
            if share.status != 'approved':
                share.status = 'approved'
                share.save()
                
                # Update user profile shares
                profile, created = UserProfile.objects.get_or_create(user=share.user)
                total_approved_shares = Share.objects.filter(
                    user=share.user, status='approved'
                ).aggregate(total=models.Sum('shares_purchased'))['total'] or 0
                profile.shares_owned = total_approved_shares
                
                # Reactivate user if shares are sufficient
                if profile.shares_owned > 20 and profile.is_deactivated:
                    profile.is_deactivated = False
                    profile.status = 'active'
                
                profile.save()
        
        self.message_user(request, f'{queryset.count()} share purchases approved and user profiles updated.')
    approve_shares.short_description = 'Approve selected share purchases'
    
    def reject_shares(self, request, queryset):
        queryset.update(status='rejected')
        self.message_user(request, f'{queryset.count()} share purchases rejected.')
    reject_shares.short_description = 'Reject selected share purchases'

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subject', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at']
    search_fields = ['name', 'email', 'subject']
    readonly_fields = ['created_at']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'membership_type', 'shares_owned', 'status', 'shares_color_display', 'is_deactivated']
    list_filter = ['membership_type', 'status', 'is_deactivated']
    search_fields = ['user__username', 'user__email']
    actions = ['activate_users', 'deactivate_users']
    
    def shares_color_display(self, obj):
        color = obj.get_shares_color()
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} shares</span>',
            color, obj.shares_owned
        )
    shares_color_display.short_description = 'Shares Status'
    
    def activate_users(self, request, queryset):
        queryset.update(is_deactivated=False, status='active')
        self.message_user(request, f'{queryset.count()} users activated.')
    activate_users.short_description = 'Activate selected users'
    
    def deactivate_users(self, request, queryset):
        queryset.update(is_deactivated=True, status='inactive')
        self.message_user(request, f'{queryset.count()} users deactivated.')
    deactivate_users.short_description = 'Deactivate selected users'

@admin.register(ShareDeduction)
class ShareDeductionAdmin(admin.ModelAdmin):
    list_display = ['reason', 'shares_deducted', 'total_remaining_shares', 'created_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['reason', 'created_by__username']
    readonly_fields = ['created_at']

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'title']
    readonly_fields = ['created_at']

@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ['title', 'date', 'time', 'meeting_type', 'is_active', 'created_by']
    list_filter = ['meeting_type', 'is_active', 'date']
    search_fields = ['title', 'location']
    readonly_fields = ['created_at']

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'announcement_type', 'is_active', 'created_by', 'created_at']
    list_filter = ['announcement_type', 'is_active', 'created_at']
    search_fields = ['title', 'content']
    readonly_fields = ['created_at']

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'recipient', 'subject', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at']
    search_fields = ['sender__username', 'recipient__username', 'subject']
    readonly_fields = ['created_at']