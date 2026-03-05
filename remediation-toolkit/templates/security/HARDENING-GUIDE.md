# AI Agent API Security Hardening Guide

**Purpose**: Comprehensive security hardening checklist and implementation guide for AI agent APIs  
**Scope**: Production AI agent systems, APIs, and supporting infrastructure  
**Last Updated**: [Date]  
**Version**: [Version Number]  

---

## Security Hardening Checklist Overview

### Implementation Priority
- **Critical (P1)**: Immediate security risks, implement within 48 hours
- **High (P2)**: Important security measures, implement within 1 week  
- **Medium (P3)**: Security enhancements, implement within 1 month
- **Low (P4)**: Security optimizations, implement as resources permit

### Compliance Score: ___/100
Use this guide to achieve and maintain a security score of 80+ for production systems.

---

## 1. Authentication and Authorization

### 1.1 API Authentication (Priority: P1)

#### Multi-Factor Authentication (MFA)
**Implementation Checklist**:
- [ ] **API Keys + Additional Factor**: Require API key plus time-based OTP or certificate
- [ ] **OAuth 2.0 with PKCE**: Implement OAuth 2.0 with Proof Key for Code Exchange
- [ ] **JWT with Short Expiry**: Use JWT tokens with 15-minute expiry and refresh tokens
- [ ] **Certificate-Based Auth**: Implement mutual TLS (mTLS) for high-security environments

**Code Example - JWT Implementation**:
```python
import jwt
from datetime import datetime, timedelta
from functools import wraps

def generate_jwt_token(user_id, secret_key):
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(minutes=15),
        'iat': datetime.utcnow(),
        'iss': 'your-ai-agent-api'
    }
    return jwt.encode(payload, secret_key, algorithm='HS256')

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return {'error': 'No authentication token provided'}, 401
        try:
            # Verify JWT token
            payload = jwt.decode(token.split(' ')[1], SECRET_KEY, algorithms=['HS256'])
            current_user = get_user(payload['user_id'])
        except jwt.ExpiredSignatureError:
            return {'error': 'Token has expired'}, 401
        except jwt.InvalidTokenError:
            return {'error': 'Invalid token'}, 401
        return f(current_user, *args, **kwargs)
    return decorated_function
```

#### API Key Security
**Implementation Checklist**:
- [ ] **Secure Key Generation**: Use cryptographically secure random generation (32+ bytes)
- [ ] **Key Rotation**: Implement automatic key rotation every 90 days
- [ ] **Key Scoping**: Limit keys to specific API endpoints and operations
- [ ] **Key Revocation**: Immediate revocation capability with audit trail

**API Key Best Practices**:
```python
import secrets
import hashlib
from datetime import datetime, timedelta

class APIKeyManager:
    def generate_api_key(self, user_id, scope=['read'], expires_days=90):
        # Generate cryptographically secure key
        key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        
        # Store in database
        api_key_record = {
            'key_hash': key_hash,
            'user_id': user_id,
            'scope': scope,
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(days=expires_days),
            'is_active': True
        }
        db.api_keys.insert(api_key_record)
        return key
    
    def validate_key(self, key, required_scope):
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        record = db.api_keys.find_one({'key_hash': key_hash, 'is_active': True})
        
        if not record:
            return False, "Invalid API key"
        if datetime.utcnow() > record['expires_at']:
            return False, "API key expired"
        if required_scope not in record['scope']:
            return False, "Insufficient permissions"
        
        return True, record
```

### 1.2 Role-Based Access Control (RBAC) (Priority: P1)

#### Permission Framework
**Implementation Checklist**:
- [ ] **Least Privilege**: Default deny, explicit allow permissions
- [ ] **Role Hierarchy**: Define clear role inheritance (user → admin → super_admin)
- [ ] **Resource-Level Permissions**: Control access to specific AI models/endpoints
- [ ] **Time-Based Permissions**: Support for temporary elevated access

**RBAC Implementation Example**:
```python
class Permission:
    # AI Agent specific permissions
    AI_CHAT = "ai:chat"
    AI_GENERATE_CODE = "ai:generate_code"
    AI_ANALYZE_DATA = "ai:analyze_data"
    AI_ADMIN = "ai:admin"
    
    # General permissions
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    BILLING_READ = "billing:read"

class Role:
    GUEST = "guest"
    USER = "user"
    PREMIUM = "premium"
    ADMIN = "admin"

ROLE_PERMISSIONS = {
    Role.GUEST: [Permission.AI_CHAT],
    Role.USER: [Permission.AI_CHAT, Permission.USER_READ],
    Role.PREMIUM: [Permission.AI_CHAT, Permission.AI_GENERATE_CODE, 
                   Permission.AI_ANALYZE_DATA, Permission.USER_READ],
    Role.ADMIN: ["*"]  # All permissions
}

def check_permission(user_role, required_permission):
    permissions = ROLE_PERMISSIONS.get(user_role, [])
    return required_permission in permissions or "*" in permissions
```

---

## 2. Rate Limiting and Traffic Control

### 2.1 Request Rate Limiting (Priority: P1)

#### Multi-Tier Rate Limiting
**Implementation Checklist**:
- [ ] **Per-User Rate Limits**: Prevent abuse by individual users
- [ ] **Per-IP Rate Limits**: Network-level protection
- [ ] **Global Rate Limits**: Protect overall system capacity
- [ ] **Adaptive Rate Limits**: Dynamic adjustment based on system load

**Rate Limiting Implementation**:
```python
import redis
from datetime import datetime, timedelta
from flask import request

class RateLimiter:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    def is_allowed(self, identifier, limit_per_minute=60, window_minutes=1):
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=window_minutes)
        
        # Use sliding window approach
        pipe = self.redis.pipeline()
        key = f"rate_limit:{identifier}"
        
        # Remove expired entries
        pipe.zremrangebyscore(key, 0, window_start.timestamp())
        
        # Count current requests
        pipe.zcount(key, window_start.timestamp(), now.timestamp())
        
        # Add current request
        pipe.zadd(key, {str(now.timestamp()): now.timestamp()})
        
        # Set expiration
        pipe.expire(key, window_minutes * 60)
        
        results = pipe.execute()
        request_count = results[1]
        
        return request_count < limit_per_minute

# Usage with different rate limits by user tier
RATE_LIMITS = {
    'guest': 10,      # 10 requests per minute
    'user': 60,       # 60 requests per minute
    'premium': 300,   # 300 requests per minute
    'admin': 1000     # 1000 requests per minute
}

@app.before_request
def apply_rate_limiting():
    user_tier = get_user_tier(request)
    limit = RATE_LIMITS.get(user_tier, 10)
    
    if not rate_limiter.is_allowed(request.remote_addr, limit):
        return {'error': 'Rate limit exceeded'}, 429
```

### 2.2 Request Size and Complexity Limits (Priority: P2)

#### Input Validation Limits
**Implementation Checklist**:
- [ ] **Maximum Request Size**: Limit payload to reasonable size (e.g., 1MB)
- [ ] **Input Length Limits**: Prevent extremely long prompts (e.g., 10K characters)
- [ ] **Complexity Scoring**: Detect and limit computationally expensive requests
- [ ] **Queue Management**: Fair scheduling for concurrent requests

**Request Validation Example**:
```python
class RequestValidator:
    MAX_PAYLOAD_SIZE = 1024 * 1024  # 1MB
    MAX_PROMPT_LENGTH = 10000       # 10K characters
    MAX_CONVERSATION_LENGTH = 50    # 50 exchanges
    
    def validate_request(self, request_data):
        errors = []
        
        # Check payload size
        if len(str(request_data)) > self.MAX_PAYLOAD_SIZE:
            errors.append("Request payload too large")
        
        # Check prompt length
        prompt = request_data.get('prompt', '')
        if len(prompt) > self.MAX_PROMPT_LENGTH:
            errors.append("Prompt too long")
        
        # Check conversation history
        conversation = request_data.get('conversation_history', [])
        if len(conversation) > self.MAX_CONVERSATION_LENGTH:
            errors.append("Conversation history too long")
        
        # Calculate complexity score
        complexity = self.calculate_complexity(request_data)
        if complexity > 100:  # Custom threshold
            errors.append("Request too complex")
        
        return len(errors) == 0, errors
    
    def calculate_complexity(self, request_data):
        # Simple complexity scoring example
        score = 0
        prompt = request_data.get('prompt', '')
        
        # Length factor
        score += len(prompt) / 100
        
        # Keyword complexity
        complex_keywords = ['analyze', 'generate', 'create', 'solve', 'calculate']
        score += sum(1 for keyword in complex_keywords if keyword in prompt.lower()) * 10
        
        return score
```

---

## 3. Input Validation and Sanitization

### 3.1 Prompt Injection Prevention (Priority: P1)

#### Input Sanitization Pipeline
**Implementation Checklist**:
- [ ] **Prompt Injection Detection**: Scan for common injection patterns
- [ ] **Content Filtering**: Remove or flag harmful content requests
- [ ] **Input Normalization**: Standardize input format and encoding
- [ ] **Escape Sequence Handling**: Properly handle special characters

**Prompt Injection Detection**:
```python
import re
from typing import List, Tuple

class PromptInjectionDetector:
    def __init__(self):
        self.injection_patterns = [
            r'ignore\s+(previous|above|prior|all)\s+instructions',
            r'forget\s+(everything|all|previous)',
            r'act\s+as\s+(a\s+)?different',
            r'pretend\s+(to\s+be|you\s+are)',
            r'roleplay\s+as',
            r'new\s+instructions?',
            r'system\s+prompt',
            r'developer\s+mode',
            r'admin\s+mode',
            r'debug\s+mode',
        ]
        
        self.suspicious_patterns = [
            r'\\n\\n',  # Attempting to break out of context
            r'\[INST\]',  # Instruction tokens
            r'<\|.*?\|>',  # Special tokens
            r'###',       # Markdown headers often used in prompts
        ]
    
    def scan_input(self, text: str) -> Tuple[bool, List[str], int]:
        """
        Returns: (is_safe, detected_patterns, risk_score)
        """
        text_lower = text.lower()
        detected_patterns = []
        risk_score = 0
        
        # Check for injection patterns
        for pattern in self.injection_patterns:
            if re.search(pattern, text_lower):
                detected_patterns.append(pattern)
                risk_score += 10
        
        # Check for suspicious patterns
        for pattern in self.suspicious_patterns:
            if re.search(pattern, text):
                detected_patterns.append(pattern)
                risk_score += 5
        
        # Additional risk factors
        if len(text) > 5000:
            risk_score += 3
        if text.count('\\') > 20:
            risk_score += 5
        if re.search(r'[A-Z]{10,}', text):  # Excessive caps
            risk_score += 2
        
        is_safe = risk_score < 15  # Adjust threshold as needed
        return is_safe, detected_patterns, risk_score
    
    def sanitize_input(self, text: str) -> str:
        """
        Clean potentially harmful input while preserving legitimate content
        """
        # Remove excessive whitespace and newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'\s{3,}', ' ', text)
        
        # Remove potential prompt tokens
        text = re.sub(r'<\|.*?\|>', '', text)
        text = re.sub(r'\[INST\].*?\[/INST\]', '', text)
        
        # Normalize encoding
        text = text.encode('utf-8', 'ignore').decode('utf-8')
        
        return text.strip()

# Usage in API endpoint
@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    data = request.json
    prompt = data.get('prompt', '')
    
    # Validate and scan input
    is_safe, patterns, risk_score = injection_detector.scan_input(prompt)
    
    if not is_safe:
        return {
            'error': 'Input blocked for security reasons',
            'risk_score': risk_score,
            'detected_patterns': patterns
        }, 400
    
    # Sanitize input
    clean_prompt = injection_detector.sanitize_input(prompt)
    
    # Process with AI model
    response = ai_model.generate(clean_prompt)
    return {'response': response}
```

### 3.2 Data Type and Format Validation (Priority: P2)

#### Schema Validation
**Implementation Checklist**:
- [ ] **JSON Schema Validation**: Enforce strict input schemas
- [ ] **Data Type Checking**: Validate all input data types
- [ ] **Range Validation**: Check numerical values are within bounds
- [ ] **Format Validation**: Validate emails, URLs, dates, etc.

**Schema Validation Example**:
```python
from jsonschema import validate, ValidationError

# Define API request schemas
CHAT_REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
            "minLength": 1,
            "maxLength": 10000
        },
        "conversation_history": {
            "type": "array",
            "maxItems": 50,
            "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "enum": ["user", "assistant"]},
                    "content": {"type": "string", "maxLength": 5000}
                },
                "required": ["role", "content"]
            }
        },
        "temperature": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 2.0
        },
        "max_tokens": {
            "type": "integer",
            "minimum": 1,
            "maximum": 4096
        }
    },
    "required": ["prompt"],
    "additionalProperties": False
}

def validate_chat_request(data):
    try:
        validate(instance=data, schema=CHAT_REQUEST_SCHEMA)
        return True, None
    except ValidationError as e:
        return False, str(e)

# Custom validators for specific fields
def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_url(url):
    pattern = r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?$'
    return bool(re.match(pattern, url))
```

---

## 4. Dependency Management and Supply Chain Security

### 4.1 Dependency Scanning and Management (Priority: P2)

#### Automated Security Scanning
**Implementation Checklist**:
- [ ] **Vulnerability Scanning**: Regular scanning with tools like Snyk, Safety, or Bandit
- [ ] **Dependency Pinning**: Pin all dependencies to specific versions
- [ ] **SBOM Generation**: Maintain Software Bill of Materials
- [ ] **License Compliance**: Track and verify open source licenses

**Dependency Security Automation**:
```yaml
# .github/workflows/security-scan.yml
name: Security Scan

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  schedule:
    - cron: '0 6 * * 1'  # Weekly on Monday

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install safety bandit semgrep
        pip install -r requirements.txt
    
    - name: Run Safety (dependency vulnerability check)
      run: safety check --json --output safety-report.json
    
    - name: Run Bandit (code security scan)
      run: bandit -r . -f json -o bandit-report.json
    
    - name: Run Semgrep (SAST)
      run: semgrep --config=auto --json --output=semgrep-report.json .
    
    - name: Upload security reports
      uses: actions/upload-artifact@v3
      with:
        name: security-reports
        path: '*-report.json'
```

**Requirements.txt Security Practices**:
```text
# Pin all dependencies to specific versions
flask==2.3.3
gunicorn==21.2.0
redis==4.6.0
psycopg2-binary==2.9.7
cryptography==41.0.4
bcrypt==4.0.1

# Security-focused packages
python-decouple==3.8      # Environment variable management
authlib==1.2.1            # OAuth and JWT
requests==2.31.0          # HTTP library with security fixes
urllib3==2.0.4           # URL handling security

# Development and testing (use separate requirements-dev.txt)
# pytest==7.4.2
# black==23.7.0
# flake8==6.0.0
```

### 4.2 Secure Package Sources (Priority: P2)

**Implementation Checklist**:
- [ ] **Trusted Repositories**: Use only trusted package repositories
- [ ] **Package Integrity**: Verify package checksums and signatures
- [ ] **Private Registry**: Consider private package registry for critical dependencies
- [ ] **Dependency Review**: Manual review of new dependencies

---

## 5. Logging and Monitoring

### 5.1 Security Event Logging (Priority: P1)

#### Comprehensive Security Logging
**Implementation Checklist**:
- [ ] **Authentication Events**: All login attempts, API key usage
- [ ] **Authorization Failures**: Access denied events
- [ ] **Input Validation Failures**: Blocked malicious inputs
- [ ] **Rate Limiting Events**: Blocked requests due to rate limits
- [ ] **System Errors**: Application and infrastructure errors

**Security Event Logger Implementation**:
```python
import logging
import json
from datetime import datetime
from flask import request, g

class SecurityEventLogger:
    def __init__(self):
        self.logger = logging.getLogger('security')
        handler = logging.FileHandler('/var/log/ai-agent/security.log')
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_event(self, event_type, details, severity='INFO'):
        """
        Log security event with structured data
        """
        event_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'severity': severity,
            'details': details,
            'request_info': {
                'ip': getattr(request, 'remote_addr', 'unknown'),
                'user_agent': getattr(request, 'headers', {}).get('User-Agent', 'unknown'),
                'endpoint': getattr(request, 'endpoint', 'unknown'),
                'method': getattr(request, 'method', 'unknown'),
                'user_id': getattr(g, 'user_id', 'anonymous')
            }
        }
        
        log_message = json.dumps(event_data)
        
        if severity == 'CRITICAL':
            self.logger.critical(log_message)
        elif severity == 'ERROR':
            self.logger.error(log_message)
        elif severity == 'WARNING':
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)

# Usage examples
security_logger = SecurityEventLogger()

# Authentication failure
security_logger.log_event(
    'auth_failure',
    {'reason': 'invalid_token', 'token_prefix': token[:8]},
    'WARNING'
)

# Rate limit exceeded
security_logger.log_event(
    'rate_limit_exceeded',
    {'limit': 100, 'requests_made': 150},
    'WARNING'
)

# Suspicious prompt detected
security_logger.log_event(
    'prompt_injection_detected',
    {'risk_score': 25, 'patterns': ['ignore previous instructions']},
    'CRITICAL'
)
```

### 5.2 Real-time Monitoring and Alerting (Priority: P1)

#### Security Monitoring Dashboard
**Implementation Checklist**:
- [ ] **Failed Authentication Monitoring**: Alert on suspicious login patterns
- [ ] **Anomaly Detection**: Unusual usage patterns or spikes
- [ ] **Error Rate Monitoring**: High error rates indicating attacks
- [ ] **Performance Monitoring**: Response time and availability
- [ ] **Business Logic Alerts**: AI-specific security events

**Monitoring Setup Example**:
```python
import time
from collections import defaultdict, deque
from threading import Thread, Lock

class SecurityMonitor:
    def __init__(self):
        self.failed_auths = defaultdict(deque)  # IP -> timestamps
        self.request_counts = defaultdict(deque)  # User -> timestamps
        self.error_rates = deque(maxlen=100)  # Recent error rates
        self.lock = Lock()
        
        # Start monitoring thread
        self.monitoring_thread = Thread(target=self._monitor_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
    
    def record_failed_auth(self, ip_address):
        with self.lock:
            current_time = time.time()
            self.failed_auths[ip_address].append(current_time)
            
            # Keep only last hour of failures
            cutoff_time = current_time - 3600
            while (self.failed_auths[ip_address] and 
                   self.failed_auths[ip_address][0] < cutoff_time):
                self.failed_auths[ip_address].popleft()
    
    def record_request(self, user_id):
        with self.lock:
            current_time = time.time()
            self.request_counts[user_id].append(current_time)
            
            # Keep only last 5 minutes
            cutoff_time = current_time - 300
            while (self.request_counts[user_id] and 
                   self.request_counts[user_id][0] < cutoff_time):
                self.request_counts[user_id].popleft()
    
    def _monitor_loop(self):
        while True:
            try:
                self._check_failed_auth_patterns()
                self._check_usage_anomalies()
                self._check_error_rates()
                time.sleep(60)  # Check every minute
            except Exception as e:
                print(f"Monitoring error: {e}")
    
    def _check_failed_auth_patterns(self):
        with self.lock:
            for ip, failures in self.failed_auths.items():
                if len(failures) > 10:  # More than 10 failures in an hour
                    self._send_alert(
                        'suspicious_auth_activity',
                        f'IP {ip} has {len(failures)} failed auth attempts in the last hour'
                    )
    
    def _send_alert(self, alert_type, message):
        # Implement your alerting mechanism (email, Slack, PagerDuty, etc.)
        print(f"SECURITY ALERT [{alert_type}]: {message}")
        # Example: send to logging system or alert service
        security_logger.log_event(alert_type, {'message': message}, 'CRITICAL')
```

---

## 6. Secrets Management

### 6.1 Secure Secret Storage (Priority: P1)

#### Secret Management Best Practices
**Implementation Checklist**:
- [ ] **Environment Variables**: Never hardcode secrets in code
- [ ] **Secret Management Service**: Use AWS Secrets Manager, HashiCorp Vault, etc.
- [ ] **Encryption at Rest**: All secrets encrypted when stored
- [ ] **Access Controls**: Role-based access to secrets
- [ ] **Secret Rotation**: Automatic rotation of sensitive credentials

**Secrets Management Implementation**:
```python
import os
import boto3
import json
from botocore.exceptions import ClientError

class SecretsManager:
    def __init__(self, region_name='us-east-1'):
        self.session = boto3.session.Session()
        self.client = self.session.client(
            service_name='secretsmanager',
            region_name=region_name
        )
    
    def get_secret(self, secret_name):
        """
        Retrieve secret from AWS Secrets Manager
        """
        try:
            get_secret_value_response = self.client.get_secret_value(
                SecretId=secret_name
            )
        except ClientError as e:
            raise Exception(f"Failed to retrieve secret {secret_name}: {e}")
        
        secret = get_secret_value_response['SecretString']
        return json.loads(secret)
    
    def get_database_credentials(self):
        """
        Get database connection details
        """
        return self.get_secret('ai-agent-db-credentials')
    
    def get_api_keys(self):
        """
        Get third-party API keys
        """
        return self.get_secret('ai-agent-api-keys')

# Environment-based configuration
class Config:
    def __init__(self):
        self.secrets_manager = SecretsManager()
        
        # Database configuration
        if os.getenv('ENV') == 'production':
            db_creds = self.secrets_manager.get_database_credentials()
            self.DATABASE_URL = f"postgresql://{db_creds['username']}:{db_creds['password']}@{db_creds['host']}:{db_creds['port']}/{db_creds['dbname']}"
        else:
            self.DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://localhost/ai_agent_dev')
        
        # API keys
        if os.getenv('ENV') == 'production':
            api_keys = self.secrets_manager.get_api_keys()
            self.OPENAI_API_KEY = api_keys['openai_api_key']
            self.JWT_SECRET_KEY = api_keys['jwt_secret_key']
        else:
            self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
            self.JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')

# Usage
config = Config()
```

### 6.2 Secret Rotation and Lifecycle Management (Priority: P2)

**Implementation Checklist**:
- [ ] **Automatic Rotation**: Implement automatic secret rotation
- [ ] **Grace Periods**: Support for gradual secret rotation
- [ ] **Audit Trails**: Log all secret access and rotation events
- [ ] **Emergency Procedures**: Process for emergency secret revocation

---

## 7. Network Security

### 7.1 HTTPS and TLS Configuration (Priority: P1)

#### TLS Best Practices
**Implementation Checklist**:
- [ ] **TLS 1.3 Minimum**: Disable older TLS versions
- [ ] **Strong Cipher Suites**: Use only secure cipher suites
- [ ] **HSTS Headers**: Implement HTTP Strict Transport Security
- [ ] **Certificate Management**: Automated certificate renewal
- [ ] **Certificate Pinning**: Pin certificates for API clients

**Nginx TLS Configuration**:
```nginx
# /etc/nginx/sites-available/ai-agent-api
server {
    listen 443 ssl http2;
    server_name api.yourai-agent.com;
    
    # SSL Configuration
    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;
    
    # TLS 1.3 only
    ssl_protocols TLSv1.3;
    
    # Strong ciphers only
    ssl_ciphers ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS;
    ssl_prefer_server_ciphers off;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
    
    # CSP for API (adjust based on your needs)
    add_header Content-Security-Policy "default-src 'none'; frame-ancestors 'none';";
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Security headers for proxied requests
        proxy_hide_header X-Powered-By;
        proxy_hide_header Server;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name api.yourai-agent.com;
    return 301 https://$server_name$request_uri;
}
```

### 7.2 Network Segmentation and Firewalls (Priority: P2)

#### Network Architecture Security
**Implementation Checklist**:
- [ ] **DMZ Configuration**: AI API in demilitarized zone
- [ ] **Internal Network Isolation**: Separate networks for different components
- [ ] **Firewall Rules**: Restrictive firewall with whitelist approach
- [ ] **VPN Access**: Secure admin access through VPN
- [ ] **Network Monitoring**: Monitor for unusual network activity

**Firewall Rules Example (iptables)**:
```bash
#!/bin/bash
# AI Agent API Firewall Rules

# Clear existing rules
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X

# Default policies
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Allow loopback
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Allow established connections
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Allow SSH (restrict to admin IPs)
iptables -A INPUT -p tcp --dport 22 -s 192.168.1.0/24 -j ACCEPT

# Allow HTTPS only
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Allow HTTP for redirect only
iptables -A INPUT -p tcp --dport 80 -j ACCEPT

# Block all other traffic
iptables -A INPUT -j DROP

# Log dropped packets
iptables -A INPUT -m limit --limit 5/min -j LOG --log-prefix "iptables denied: " --log-level 7

# Save rules
iptables-save > /etc/iptables/rules.v4
```

---

## 8. Application Security Headers

### 8.1 Security Headers Implementation (Priority: P2)

**Implementation Checklist**:
- [ ] **Content Security Policy (CSP)**: Prevent XSS attacks
- [ ] **HSTS**: Force HTTPS connections
- [ ] **X-Frame-Options**: Prevent clickjacking
- [ ] **X-Content-Type-Options**: Prevent MIME sniffing
- [ ] **Referrer Policy**: Control referrer information

**Security Headers in Flask**:
```python
from flask import Flask, request, make_response
import secrets

app = Flask(__name__)

# Generate a nonce for each request
def generate_nonce():
    return secrets.token_urlsafe(16)

@app.after_request
def add_security_headers(response):
    # Content Security Policy
    nonce = generate_nonce()
    csp = (
        f"default-src 'none'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        f"style-src 'self' 'unsafe-inline'; "
        f"img-src 'self' data:; "
        f"connect-src 'self'; "
        f"frame-ancestors 'none'; "
        f"base-uri 'self'; "
        f"form-action 'self'"
    )
    response.headers['Content-Security-Policy'] = csp
    
    # HSTS
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    # Clickjacking protection
    response.headers['X-Frame-Options'] = 'DENY'
    
    # MIME sniffing protection
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # XSS protection
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # Referrer policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Additional security headers
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    
    return response

@app.route('/api/health')
def health_check():
    return {'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}
```

---

## 9. Error Handling and Information Disclosure

### 9.1 Secure Error Handling (Priority: P1)

**Implementation Checklist**:
- [ ] **Generic Error Messages**: Don't expose internal details
- [ ] **Error Logging**: Log detailed errors internally only
- [ ] **Status Code Consistency**: Consistent HTTP status codes
- [ ] **Debug Mode Disabled**: Never enable debug mode in production

**Secure Error Handler**:
```python
from flask import Flask, jsonify, current_app
import traceback
import logging

app = Flask(__name__)

# Configure error logging
error_logger = logging.getLogger('errors')
error_handler = logging.FileHandler('/var/log/ai-agent/errors.log')
error_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s %(name)s %(message)s'
))
error_logger.addHandler(error_handler)
error_logger.setLevel(logging.ERROR)

class SecurityError(Exception):
    """Custom exception for security-related errors"""
    pass

@app.errorhandler(Exception)
def handle_unexpected_error(error):
    # Log the full error internally
    error_id = secrets.token_hex(8)
    error_logger.error(f"Error {error_id}: {str(error)}\n{traceback.format_exc()}")
    
    # Return generic error to user
    return jsonify({
        'error': 'An internal error occurred',
        'error_id': error_id,
        'timestamp': datetime.utcnow().isoformat()
    }), 500

@app.errorhandler(SecurityError)
def handle_security_error(error):
    # Log security errors with high priority
    error_id = secrets.token_hex(8)
    security_logger.log_event(
        'security_error',
        {'error_id': error_id, 'message': str(error)},
        'CRITICAL'
    )
    
    return jsonify({
        'error': 'Security validation failed',
        'error_id': error_id
    }), 403

@app.errorhandler(429)
def handle_rate_limit(error):
    return jsonify({
        'error': 'Rate limit exceeded',
        'retry_after': '60'
    }), 429

@app.errorhandler(400)
def handle_bad_request(error):
    return jsonify({
        'error': 'Invalid request format',
        'message': 'Please check your request and try again'
    }), 400

@app.errorhandler(401)
def handle_unauthorized(error):
    return jsonify({
        'error': 'Authentication required',
        'message': 'Please provide valid authentication credentials'
    }), 401

@app.errorhandler(403)
def handle_forbidden(error):
    return jsonify({
        'error': 'Access denied',
        'message': 'You do not have permission to access this resource'
    }), 403

@app.errorhandler(404)
def handle_not_found(error):
    return jsonify({
        'error': 'Resource not found',
        'message': 'The requested resource does not exist'
    }), 404
```

---

## 10. Security Testing and Validation

### 10.1 Automated Security Testing (Priority: P2)

**Implementation Checklist**:
- [ ] **SAST (Static Analysis)**: Code security scanning
- [ ] **DAST (Dynamic Analysis)**: Runtime security testing
- [ ] **Dependency Scanning**: Automated vulnerability detection
- [ ] **Penetration Testing**: Regular professional security assessment

**Security Testing Pipeline**:
```yaml
# .github/workflows/security-testing.yml
name: Security Testing

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  sast:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Run Semgrep
      uses: returntocorp/semgrep-action@v1
      with:
        config: >-
          p/security-audit
          p/secrets
          p/owasp-top-ten
    
    - name: Run CodeQL
      uses: github/codeql-action/init@v2
      with:
        languages: python
    
    - name: Perform CodeQL Analysis
      uses: github/codeql-action/analyze@v2

  dependency-check:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install safety pip-audit
        pip install -r requirements.txt
    
    - name: Run Safety
      run: safety check --json --output safety-report.json
    
    - name: Run pip-audit
      run: pip-audit --output pip-audit-report.json --format json

  dast:
    runs-on: ubuntu-latest
    needs: [sast, dependency-check]
    steps:
    - uses: actions/checkout@v3
    
    - name: Start application
      run: |
        docker-compose up -d
        sleep 30
    
    - name: Run OWASP ZAP
      uses: zaproxy/action-full-scan@v0.4.0
      with:
        target: 'http://localhost:8000'
        rules_file_name: '.zap/rules.tsv'
        cmd_options: '-a'
```

### 10.2 Security Monitoring and Metrics (Priority: P2)

**Key Security Metrics to Track**:
- [ ] **Failed Authentication Rate**: Monitor for brute force attacks
- [ ] **Rate Limit Trigger Rate**: Identify abuse patterns
- [ ] **Error Rate by Endpoint**: Detect potential attacks
- [ ] **Response Time Anomalies**: Identify DoS attacks
- [ ] **Unusual Usage Patterns**: Machine learning-based anomaly detection

---

## 11. Incident Response and Recovery

### 11.1 Security Incident Response Plan (Priority: P1)

**Implementation Checklist**:
- [ ] **Incident Detection**: Automated alerting for security events
- [ ] **Response Team**: Designated security incident response team
- [ ] **Communication Plan**: Clear escalation and communication procedures
- [ ] **Recovery Procedures**: Documented steps for system recovery
- [ ] **Post-Incident Analysis**: Process for learning and improvement

**Security Incident Response Playbook**:
```python
class SecurityIncidentResponse:
    def __init__(self):
        self.alert_channels = {
            'email': 'security-team@yourcompany.com',
            'slack': '#security-alerts',
            'pager': '+1234567890'
        }
        
    def detect_incident(self, event_type, severity, details):
        """
        Incident detection and initial response
        """
        incident_id = self.generate_incident_id()
        
        # Log the incident
        incident_data = {
            'incident_id': incident_id,
            'event_type': event_type,
            'severity': severity,
            'details': details,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'detected'
        }
        
        # Send alerts based on severity
        if severity == 'CRITICAL':
            self.send_immediate_alert(incident_data)
            self.activate_response_team()
        elif severity == 'HIGH':
            self.send_alert(incident_data)
        
        # Begin automated response
        if event_type == 'auth_brute_force':
            self.block_ip_address(details.get('ip_address'))
        elif event_type == 'prompt_injection':
            self.enable_enhanced_filtering()
        
        return incident_id
    
    def block_ip_address(self, ip_address):
        """
        Automatically block suspicious IP addresses
        """
        # Add to blocklist
        blocklist.add(ip_address, duration='1h', reason='security_incident')
        
        # Update firewall rules if needed
        self.update_firewall_rules()
    
    def generate_incident_id(self):
        return f"SEC-{datetime.utcnow().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
```

---

## 12. Compliance and Documentation

### 12.1 Security Documentation (Priority: P2)

**Required Documentation**:
- [ ] **Security Architecture Diagram**: Visual representation of security controls
- [ ] **Threat Model**: Documented threats and mitigations
- [ ] **Security Policies**: Written security policies and procedures
- [ ] **Audit Trails**: Comprehensive logging and monitoring documentation
- [ ] **Incident Response Procedures**: Step-by-step response procedures

---

## Implementation Timeline

### Phase 1: Critical Security (Week 1-2)
- [ ] Implement authentication and authorization
- [ ] Deploy input validation and sanitization
- [ ] Set up security logging and monitoring
- [ ] Configure HTTPS and security headers

### Phase 2: Enhanced Protection (Week 3-4)
- [ ] Deploy rate limiting and traffic controls
- [ ] Implement secrets management
- [ ] Set up dependency scanning
- [ ] Configure network security

### Phase 3: Advanced Security (Week 5-8)
- [ ] Deploy advanced monitoring and alerting
- [ ] Implement automated security testing
- [ ] Set up incident response procedures
- [ ] Complete security documentation

### Phase 4: Continuous Improvement (Ongoing)
- [ ] Regular security assessments
- [ ] Ongoing monitoring and optimization
- [ ] Team training and awareness
- [ ] Process refinement

---

## Security Checklist Summary

Use this checklist for regular security reviews:

### Authentication & Authorization
- [ ] Multi-factor authentication implemented
- [ ] Role-based access control configured
- [ ] API key security measures in place
- [ ] Session management secure

### Input Validation
- [ ] Prompt injection protection active
- [ ] Input sanitization implemented
- [ ] Schema validation enforced
- [ ] Rate limiting configured

### Infrastructure Security
- [ ] HTTPS/TLS properly configured
- [ ] Security headers implemented
- [ ] Network segmentation in place
- [ ] Firewall rules restrictive

### Monitoring & Response
- [ ] Security logging comprehensive
- [ ] Real-time monitoring active
- [ ] Incident response plan tested
- [ ] Regular security assessments conducted

**Final Security Score: ___/100**

Target: Maintain 80+ for production systems, 95+ for high-security environments.

---

**This hardening guide provides comprehensive security measures for AI agent APIs. Regular review and implementation of these controls will significantly improve your security posture and protect against common threats.**

**Document Control**: [Version] | [Date] | [Approved by] | [Next review date]