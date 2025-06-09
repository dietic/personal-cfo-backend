# 👤 User Profile & Settings System

## Overview

This document describes the comprehensive user profile and settings system that matches the frontend requirements shown in the provided screenshots. The system includes profile management, notification preferences, security settings, and account management features.

## 🎯 Features Implemented

### 1. Profile Information Management

- **Name Fields**: First name and last name
- **Contact Info**: Email and phone number
- **Profile Photo**: Upload and manage profile pictures
- **Preferences**: Currency and timezone settings

### 2. Notification Preferences

- **Budget Alerts**: Notifications when approaching budget limits
- **Payment Reminders**: Upcoming card payment notifications
- **Transaction Alerts**: Large or unusual transaction notifications
- **Weekly Summary**: Weekly spending summaries
- **Monthly Reports**: Detailed monthly financial reports

### 3. Delivery Methods

- **Email Notifications**: Receive notifications via email
- **Push Notifications**: Browser/mobile push notifications

### 4. Security Settings

- **Password Management**: Update account password
- **Password Validation**: Current password verification required

### 5. Danger Zone

- **Account Deletion**: Permanent account removal
- **Confirmation Required**: Password + confirmation text verification

## 🔧 Technical Implementation

### Database Schema Enhancement

The `users` table has been enhanced with the following columns:

```sql
-- Profile Information
first_name VARCHAR
last_name VARCHAR
phone_number VARCHAR
profile_picture_url VARCHAR

-- Preferences
preferred_currency ENUM('USD', 'PEN', 'EUR', 'GBP')
timezone ENUM('UTC_MINUS_8', 'UTC_MINUS_7', 'UTC_MINUS_6', 'UTC_MINUS_5', 'UTC_MINUS_3', 'UTC_0', 'UTC_PLUS_1')

-- Notification Preferences
budget_alerts_enabled BOOLEAN
payment_reminders_enabled BOOLEAN
transaction_alerts_enabled BOOLEAN
weekly_summary_enabled BOOLEAN
monthly_reports_enabled BOOLEAN

-- Delivery Methods
email_notifications_enabled BOOLEAN
push_notifications_enabled BOOLEAN
```

### API Endpoints

#### Profile Management

```
GET    /api/v1/users/profile              # Get complete user profile
PUT    /api/v1/users/profile              # Update profile information
POST   /api/v1/users/profile/photo        # Upload profile photo
```

#### Notification Settings

```
GET    /api/v1/users/notifications        # Get notification preferences
PUT    /api/v1/users/notifications        # Update notification preferences
```

#### Security

```
PUT    /api/v1/users/password             # Update password
```

#### Account Management

```
GET    /api/v1/users/account/stats        # Get account statistics
DELETE /api/v1/users/account              # Delete account (Danger Zone)
```

### Data Models

#### Enhanced User Model

```python
class User(Base):
    # Basic fields
    id = Column(GUID(), primary_key=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    is_active = Column(Boolean, default=True)

    # Profile Information
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    profile_picture_url = Column(String, nullable=True)

    # Preferences
    preferred_currency = Column(SQLEnum(CurrencyEnum), default=CurrencyEnum.USD)
    timezone = Column(SQLEnum(TimezoneEnum), default=TimezoneEnum.UTC_MINUS_8)

    # Notification Preferences
    budget_alerts_enabled = Column(Boolean, default=True)
    payment_reminders_enabled = Column(Boolean, default=True)
    transaction_alerts_enabled = Column(Boolean, default=False)
    weekly_summary_enabled = Column(Boolean, default=True)
    monthly_reports_enabled = Column(Boolean, default=True)

    # Delivery Methods
    email_notifications_enabled = Column(Boolean, default=True)
    push_notifications_enabled = Column(Boolean, default=False)
```

#### Request/Response Schemas

```python
class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    preferred_currency: Optional[CurrencyEnum] = None
    timezone: Optional[TimezoneEnum] = None

class UserNotificationPreferences(BaseModel):
    budget_alerts_enabled: bool
    payment_reminders_enabled: bool
    transaction_alerts_enabled: bool
    weekly_summary_enabled: bool
    monthly_reports_enabled: bool
    email_notifications_enabled: bool
    push_notifications_enabled: bool

class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str
    confirm_new_password: str

class AccountDeletionRequest(BaseModel):
    password: str
    confirmation_text: str  # Must be "DELETE MY ACCOUNT"
```

## 🔒 Security Features

### Password Management

- **Current Password Verification**: Required for password changes
- **Password Confirmation**: New password must be confirmed
- **Secure Hashing**: Passwords stored using bcrypt hashing

### Account Deletion

- **Password Verification**: Current password required
- **Confirmation Text**: User must type "DELETE MY ACCOUNT"
- **Cascade Deletion**: All user data removed (cards, transactions, budgets, etc.)

### File Upload Security

- **File Type Validation**: Only image files allowed for profile photos
- **File Size Limits**: 1MB maximum file size
- **Secure Storage**: Files stored outside web root

## 🎨 Frontend Integration

### Profile Tab

- Form fields for first name, last name, email, phone number
- Currency dropdown (USD, PEN, EUR, GBP)
- Timezone dropdown with readable descriptions
- Profile photo upload with preview

### Notifications Tab

- Toggle switches for each notification type
- Separate section for delivery methods
- Real-time preference updates

### Security Tab

- Password change form with current/new/confirm fields
- Password strength validation
- Success/error feedback

### Billing Tab

- Account statistics display
- Danger Zone section with deletion button
- Confirmation modal for account deletion

## 📊 Default Settings

New users are created with the following defaults:

- **Currency**: USD
- **Timezone**: UTC-8 (Pacific Time)
- **Budget Alerts**: Enabled
- **Payment Reminders**: Enabled
- **Transaction Alerts**: Disabled
- **Weekly Summary**: Enabled
- **Monthly Reports**: Enabled
- **Email Notifications**: Enabled
- **Push Notifications**: Disabled

## 🧪 Testing

### Automated Tests

Run the comprehensive test suite:

```bash
python test_user_profile.py
```

### Manual Testing

1. **Profile Updates**: Test name, phone, currency, timezone changes
2. **Photo Upload**: Test profile picture upload (JPG, PNG, GIF)
3. **Notifications**: Toggle each notification preference
4. **Password Change**: Update password with proper verification
5. **Account Stats**: Verify statistics display correctly
6. **Account Deletion**: Test deletion with proper confirmation

### API Testing Examples

#### Update Profile

```bash
curl -X PUT "http://localhost:8000/api/v1/users/profile" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "phone_number": "+1 (555) 123-4567",
    "preferred_currency": "USD",
    "timezone": "UTC_MINUS_5"
  }'
```

#### Update Notifications

```bash
curl -X PUT "http://localhost:8000/api/v1/users/notifications" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "budget_alerts_enabled": true,
    "payment_reminders_enabled": true,
    "transaction_alerts_enabled": false,
    "weekly_summary_enabled": true,
    "monthly_reports_enabled": true,
    "email_notifications_enabled": true,
    "push_notifications_enabled": false
  }'
```

#### Change Password

```bash
curl -X PUT "http://localhost:8000/api/v1/users/password" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "oldpassword",
    "new_password": "newpassword123",
    "confirm_new_password": "newpassword123"
  }'
```

## 🚀 Deployment Notes

1. **Database Migration**: Run the profile enhancement migration

   ```bash
   alembic upgrade head
   ```

2. **File Storage**: Ensure uploads directory exists and is writable

   ```bash
   mkdir -p uploads/profile_photos
   chmod 755 uploads/profile_photos
   ```

3. **Environment Variables**: No additional environment variables required

## 📈 Future Enhancements

### Planned Features

- **Two-Factor Authentication**: Enhanced security options
- **Social Login**: OAuth integration with Google, GitHub, etc.
- **Data Export**: Allow users to export their data
- **Theme Preferences**: Light/dark mode settings
- **Language Settings**: Multi-language support

### Integration Opportunities

- **Email Service**: Connect with email service for notifications
- **Push Service**: Implement web push notifications
- **Profile Photos**: CDN integration for better performance
- **Activity Log**: Track profile changes and security events

## 🎉 Summary

The user profile and settings system is now fully implemented and matches all the features shown in the provided screenshots:

✅ **Profile Information** - Complete name, contact, and preference management
✅ **Notification Settings** - 5 notification types + 2 delivery methods
✅ **Security Management** - Password updates with verification
✅ **Account Statistics** - Comprehensive account usage data
✅ **Danger Zone** - Secure account deletion with confirmation

The system provides a modern, secure, and user-friendly profile management experience that integrates seamlessly with the existing Personal CFO application.
