from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

class MembershipApplication(models.Model):
    APPLICATION_TYPES = [
        ('single', 'Single Family'),
        ('double', 'Double Family'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    application_type = models.CharField(max_length=10, choices=APPLICATION_TYPES)
    
    # Personal Information
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    address = models.TextField()
    phone_main = models.CharField(max_length=20)
    minnesota_id = models.FileField(upload_to='ids/')
    
    # Family Information
    spouse = models.CharField(max_length=100, blank=True)
    spouse_phone = models.CharField(max_length=20, blank=True)
    authorized_rep = models.CharField(max_length=100, blank=True)
    
    # Children
    child_1 = models.CharField(max_length=100, blank=True)
    child_2 = models.CharField(max_length=100, blank=True)
    child_3 = models.CharField(max_length=100, blank=True)
    child_4 = models.CharField(max_length=100, blank=True)
    child_5 = models.CharField(max_length=100, blank=True)
    
    # Parents
    parent_1 = models.CharField(max_length=100, blank=True)
    parent_2 = models.CharField(max_length=100, blank=True)
    
    # Siblings
    sibling_1 = models.CharField(max_length=100, blank=True)
    sibling_2 = models.CharField(max_length=100, blank=True)
    
    # Status and timestamps
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.application_type}"

class Payment(models.Model):
    PAYMENT_TYPES = [
        ('activation_fee', 'Activation Fee'),
        ('membership_single', 'Single Membership - $200'),
        ('membership_double', 'Double Membership - $400'),
        ('shares', 'Share Purchase'),
        ('other', 'Other'),
    ]
    
    PAYMENT_METHODS = [
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('cash', 'Cash'),
        ('check', 'Check'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    transaction_id = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    payment_proof = models.FileField(upload_to='payments/')
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.payment_type} - ${self.amount}"

class Claim(models.Model):
    CLAIM_TYPES = [
        ('death', 'Death Benefit'),
        ('medical', 'Medical Emergency'),
        ('education', 'Education Support'),
        ('emergency', 'Emergency Assistance'),
    ]
    
    RELATIONSHIPS = [
        ('self', 'Self'),
        ('spouse', 'Spouse'),
        ('child', 'Child'),
        ('parent', 'Parent'),
        ('sibling', 'Sibling'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    claim_type = models.CharField(max_length=20, choices=CLAIM_TYPES)
    member_name = models.CharField(max_length=100)
    relationship = models.CharField(max_length=20, choices=RELATIONSHIPS)
    incident_date = models.DateField()
    amount_requested = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    supporting_documents = models.FileField(upload_to='claims/', blank=True)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.claim_type} - ${self.amount_requested}"

class Share(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    shares_purchased = models.IntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    transaction_id = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    payment_proof = models.FileField(upload_to='shares/')
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.shares_purchased} shares"

class ContactMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.subject}"

class UserProfile(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('registered', 'Registered'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    shares_owned = models.IntegerField(default=0)
    membership_type = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='registered')
    is_deactivated = models.BooleanField(default=False)
    
    def get_shares_color(self):
        if self.shares_owned <= 20:
            return 'red'
        elif self.shares_owned < 25:
            return 'yellow'
        else:
            return 'green'
    
    def __str__(self):
        return f"{self.user.username} Profile"

class ShareDeduction(models.Model):
    reason = models.TextField()
    shares_deducted = models.IntegerField()
    total_remaining_shares = models.IntegerField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Deduction: {self.shares_deducted} shares - {self.reason[:50]}"

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('shares_low', 'Low Shares'),
        ('shares_deducted', 'Shares Deducted'),
        ('claim_submitted', 'Claim Submitted'),
        ('general', 'General'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"

class Meeting(models.Model):
    MEETING_TYPES = [
        ('general', 'General Meeting'),
        ('board', 'Board Meeting'),
        ('annual', 'Annual Meeting'),
        ('special', 'Special Meeting'),
        ('emergency', 'Emergency Meeting'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField()
    time = models.TimeField()
    location = models.CharField(max_length=200)
    meeting_type = models.CharField(max_length=20, choices=MEETING_TYPES, default='general')
    max_attendees = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} - {self.date}"

class Announcement(models.Model):
    ANNOUNCEMENT_TYPES = [
        ('general', 'General'),
        ('urgent', 'Urgent'),
        ('event', 'Event'),
        ('policy', 'Policy Update'),
    ]
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    announcement_type = models.CharField(max_length=20, choices=ANNOUNCEMENT_TYPES, default='general')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title

class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    subject = models.CharField(max_length=200)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.sender.username} to {self.recipient.username}: {self.subject}"