from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from main.models import UserProfile, ShareDeduction, Notification, Share
from django.db import models, transaction

class Command(BaseCommand):
    help = 'Deduct 1 share from all users monthly'

    def handle(self, *args, **options):
        with transaction.atomic():
            # Get all user profiles
            profiles = UserProfile.objects.all()
            total_users_affected = 0
            total_shares_deducted = 0
            
            for profile in profiles:
                if profile.shares_owned > 0:
                    # Deduct 1 share from profile
                    new_shares = max(0, profile.shares_owned - 1)
                    profile.shares_owned = new_shares
                    
                    # Check if user should be deactivated
                    if profile.shares_owned <= 20:
                        profile.is_deactivated = True
                        profile.status = 'inactive'
                        
                        # Send low shares email
                        send_mail(
                            'Account Deactivated - Low Shares Balance',
                            f'Dear {profile.user.first_name},\\n\\nYour account has been deactivated because your shares balance ({profile.shares_owned}) is below the minimum required (20 shares).\\n\\nPlease purchase more shares to reactivate your account.\\n\\nThank you.',
                            settings.DEFAULT_FROM_EMAIL,
                            [profile.user.email],
                            fail_silently=True,
                        )
                    
                    profile.save()
                    total_users_affected += 1
                    total_shares_deducted += 1
                    
                    # Create notification
                    Notification.objects.create(
                        user=profile.user,
                        notification_type='shares_deducted',
                        title='Monthly Share Deduction',
                        message=f'1 share has been automatically deducted. Remaining shares: {profile.shares_owned}'
                    )
                    
                    self.stdout.write(f'Deducted 1 share from {profile.user.username}. Remaining: {profile.shares_owned}')
            
            # Record the deduction
            if total_shares_deducted > 0:
                ShareDeduction.objects.create(
                    reason=f'Monthly automatic deduction - {timezone.now().strftime("%B %Y")}',
                    shares_deducted=total_shares_deducted,
                    total_remaining_shares=UserProfile.objects.aggregate(
                        total=models.Sum('shares_owned'))['total'] or 0,
                    created_by=User.objects.filter(is_staff=True).first()
                )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deducted {total_shares_deducted} shares from {total_users_affected} users'
                )
            )