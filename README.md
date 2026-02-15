# Aviator Game Platform - Django

A professional Aviator crash game platform similar to Betika Aviator, built with Django and real-time JavaScript.

## Features

✈️ **Real-time Aviator Game**
- Live multiplier updates
- Instant cashout functionality
- Auto-cashout option
- Round history tracking
- Provably fair game engine

💰 **Payment Integration**
- M-Pesa STK Push deposits
- M-Pesa B2C withdrawals
- Instant transaction processing
- Transaction history

👥 **User Features**
- Phone number authentication
- Welcome bonus (50 KES)
- User balance (main + bonus)
- Betting history
- User statistics & profile
- Leaderboards

💬 **Social Features**
- Live chat system
- Rain promotions (bonus giveaways)
- Active bets display

📊 **Admin Features**
- Game monitoring
- Transaction management
- User management
- Statistics tracking

## Technology Stack

- **Backend**: Django 4.2+
- **Database**: PostgreSQL (or SQLite for development)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Payment**: M-Pesa Daraja API
- **Real-time Updates**: AJAX polling

## Installation

### Prerequisites

- Python 3.8+
- PostgreSQL (optional, can use SQLite)
- M-Pesa Developer Account (for payments)

### Setup Steps

1. **Clone or create project directory**
```bash
mkdir aviator_platform
cd aviator_platform
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install Django and dependencies**
```bash
pip install django psycopg2-binary requests python-decouple
```

4. **Create Django project**
```bash
django-admin startproject config .
python manage.py startapp aviator
```

5. **Copy the provided files to your project**
- Copy `models.py` to `aviator/models.py`
- Copy `views.py` to `aviator/views.py`
- Copy `urls.py` to `aviator/urls.py`
- Copy `utils.py` to `aviator/utils.py`
- Copy `game_engine.py` to `aviator/game_engine.py`
- Create `templates` folder and copy all HTML files
- Copy settings from `settings_example.py` to `config/settings.py`

6. **Update main URLs (config/urls.py)**
```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('aviator.urls')),
]
```

7. **Configure settings**

Edit `config/settings.py`:
```python
# Add to INSTALLED_APPS
INSTALLED_APPS = [
    ...
    'aviator',
]

# Set custom user model
AUTH_USER_MODEL = 'aviator.User'

# Configure database (PostgreSQL or SQLite)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# For PostgreSQL:
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'aviator_db',
#         'USER': 'your_username',
#         'PASSWORD': 'your_password',
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }

# Templates directory
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        ...
    },
]

# M-Pesa Configuration
MPESA_ENVIRONMENT = 'sandbox'
MPESA_CONSUMER_KEY = 'your_consumer_key'
MPESA_CONSUMER_SECRET = 'your_consumer_secret'
MPESA_SHORTCODE = 'your_shortcode'
MPESA_PASSKEY = 'your_passkey'
MPESA_CALLBACK_URL = 'https://yourdomain.com/mpesa/callback/'
```

8. **Run migrations**
```bash
python manage.py makemigrations
python manage.py migrate
```

9. **Create superuser**
```bash
python manage.py createsuperuser
```

10. **Create game engine management command**

Create file `aviator/management/commands/run_game_engine.py`:
```python
from django.core.management.base import BaseCommand
from aviator.game_engine import AviatorGameEngine

class Command(BaseCommand):
    help = 'Run the Aviator game engine'

    def handle(self, *args, **options):
        engine = AviatorGameEngine()
        self.stdout.write(self.style.SUCCESS('Starting Aviator Game Engine...'))
        engine.run()
```

11. **Run the development server**
```bash
python manage.py runserver
```

12. **In a separate terminal, run the game engine**
```bash
python manage.py run_game_engine
```

## M-Pesa Integration Setup

### 1. Get M-Pesa Credentials

1. Go to [Safaricom Developer Portal](https://developer.safaricom.co.ke/)
2. Create an account and login
3. Create an app (select Lipa Na M-Pesa Online)
4. Get your credentials:
   - Consumer Key
   - Consumer Secret
   - Business Short Code
   - Passkey

### 2. Configure Callback URL

For development, use ngrok to expose your local server:
```bash
ngrok http 8000
```

Update `MPESA_CALLBACK_URL` in settings with your ngrok URL:
```python
MPESA_CALLBACK_URL = 'https://your-ngrok-url.ngrok.io/mpesa/callback/'
```

### 3. Test M-Pesa Integration

Use test credentials provided by Safaricom for sandbox environment.

## Project Structure

```
aviator_platform/
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── aviator/
│   ├── __init__.py
│   ├── models.py          # Database models
│   ├── views.py           # API endpoints and views
│   ├── urls.py            # URL routing
│   ├── utils.py           # Helper functions
│   ├── game_engine.py     # Game logic engine
│   ├── admin.py           # Django admin configuration
│   └── management/
│       └── commands/
│           └── run_game_engine.py
├── templates/
│   ├── base.html          # Base template
│   ├── game.html          # Main game interface
│   ├── login.html         # Login page
│   ├── register.html      # Registration page
│   ├── deposit.html       # Deposit page
│   ├── betting_history.html
│   ├── transactions.html
│   └── profile.html
├── static/
│   ├── css/
│   ├── js/
│   └── images/
├── manage.py
└── requirements.txt
```

## Key Features Explained

### Game Engine

The game engine (`game_engine.py`) runs independently and manages:
- Creating new rounds
- Calculating multipliers in real-time
- Processing auto-cashouts
- Determining crash points
- Updating game state

### Real-time Updates

The frontend uses AJAX polling (every 100ms) to:
- Fetch current round status
- Update multiplier display
- Update active bets list
- Process auto-cashouts

### Provably Fair

The game uses cryptographic hashing to ensure fairness:
- Server seed + Client seed + Nonce
- SHA-256 hashing
- Verifiable results

### Payment Flow

**Deposits:**
1. User initiates deposit
2. STK push sent to phone
3. User enters M-Pesa PIN
4. Callback received
5. Balance credited instantly

**Withdrawals:**
1. User requests withdrawal
2. B2C payment initiated
3. M-Pesa processes payment
4. Money sent to phone

## Usage

### Player Flow

1. **Register**: Create account with phone number
2. **Deposit**: Add funds via M-Pesa
3. **Play**: Place bets and cashout before plane flies away
4. **Withdraw**: Cash out winnings to M-Pesa

### Admin Flow

1. Access admin panel: `/admin`
2. Monitor active games
3. View transactions
4. Manage users
5. Configure system settings

## Security Considerations

1. **Never commit sensitive data**
   - Use environment variables for secrets
   - Add `.env` to `.gitignore`

2. **Production settings**
   - Set `DEBUG = False`
   - Use strong `SECRET_KEY`
   - Enable HTTPS
   - Configure ALLOWED_HOSTS

3. **Database**
   - Use PostgreSQL in production
   - Regular backups
   - Enable connection pooling

4. **M-Pesa**
   - Validate all callbacks
   - Use production credentials securely
   - Log all transactions

## Deployment

### Using Railway/Render/Heroku

1. Add `Procfile`:
```
web: gunicorn config.wsgi
worker: python manage.py run_game_engine
```

2. Add `requirements.txt`:
```
Django>=4.2
psycopg2-binary
gunicorn
requests
python-decouple
whitenoise
```

3. Configure environment variables
4. Run migrations
5. Collect static files

### Using VPS (Ubuntu)

1. Install dependencies
2. Setup PostgreSQL
3. Configure Nginx
4. Setup Gunicorn
5. Use Supervisor for game engine
6. Configure SSL with Let's Encrypt

## API Endpoints

### Authentication
- `POST /register/` - Register new user
- `POST /login/` - Login user
- `GET /logout/` - Logout user

### Game
- `GET /api/game/current-round/` - Get current round
- `GET /api/game/round-history/` - Get round history
- `POST /api/game/place-bet/` - Place a bet
- `POST /api/game/cashout/` - Cashout bet

### Transactions
- `POST /api/deposit/initiate/` - Initiate deposit
- `POST /api/withdraw/` - Request withdrawal
- `GET /api/transactions/` - Get transaction history

### Chat & Social
- `GET /api/chat/messages/` - Get chat messages
- `POST /api/chat/send/` - Send chat message
- `GET /api/rain/active/` - Get active rains
- `POST /api/rain/join/` - Join rain

## Troubleshooting

### Game engine not starting
- Ensure migrations are run
- Check database connection
- Verify models are properly imported

### M-Pesa not working
- Verify credentials are correct
- Check callback URL is accessible
- Ensure phone number format is correct
- Check M-Pesa sandbox status

### Balance not updating
- Check transaction status in database
- Verify callback is being received
- Check logs for errors

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is for educational purposes. Ensure you comply with local gambling regulations.

## Support

For issues and questions:
- Check the troubleshooting section
- Review Django documentation
- Check M-Pesa API documentation

## Future Enhancements

- [ ] WebSocket for real-time updates
- [ ] Mobile app (React Native)
- [ ] Multiple game modes
- [ ] Tournament system
- [ ] Referral program
- [ ] Progressive jackpots
- [ ] Social features (friends, challenges)
- [ ] Analytics dashboard

## Credits

Built with Django and modern web technologies.
Inspired by popular aviator games.

---

**Note**: This is a complete gambling platform. Ensure you:
1. Have proper licensing in your jurisdiction
2. Implement responsible gambling features
3. Comply with local regulations
4. Implement age verification (18+)
5. Add self-exclusion options