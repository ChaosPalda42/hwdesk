import json
from typing import List, Dict, Any


SETTINGS_SCHEMA = [
    {
        "key": "COMPANY_NAME",
        "label": "Název společnosti",
        "group": "Obecné",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "Název společnosti zobrazený v aplikaci"
    },
    {
        "key": "BASE_URL",
        "label": "Základní URL",
        "group": "Obecné",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "Základní URL adresa aplikace"
    },
    {
        "key": "PROTOCOL_COPY_TO",
        "label": "Kopie protokolu",
        "group": "Obecné",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "E-mailová adresa, na kterou se posílají kopie protokolů"
    },
    {
        "key": "HANDOVER_TOKEN_HOURS",
        "label": "Doba platnosti předání (hodiny)",
        "group": "Obecné",
        "type": "int",
        "secret": False,
        "choices": [],
        "help": "Doba platnosti předání v hodinách"
    },
    {
        "key": "AUTH_MODE",
        "label": "Režim autentizace",
        "group": "Přihlášení Microsoft 365 (Entra ID)",
        "type": "choice",
        "secret": False,
        "choices": ["dev", "oidc"],
        "help": "Režim autentizace uživatelů"
    },
    {
        "key": "OIDC_TENANT_ID",
        "label": "Tenant ID",
        "group": "Přihlášení Microsoft 365 (Entra ID)",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "Tenant ID pro přihlášení pomocí Microsoft 365"
    },
    {
        "key": "OIDC_CLIENT_ID",
        "label": "Client ID",
        "group": "Přihlášení Microsoft 365 (Entra ID)",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "Client ID pro přihlášení pomocí Microsoft 365"
    },
    {
        "key": "OIDC_CLIENT_SECRET",
        "label": "Client Secret",
        "group": "Přihlášení Microsoft 365 (Entra ID)",
        "type": "str",
        "secret": True,
        "choices": [],
        "help": "Client Secret pro přihlášení pomocí Microsoft 365"
    },
    {
        "key": "EMAIL_MODE",
        "label": "Režim e-mailové komunikace",
        "group": "E-mail (SMTP)",
        "type": "choice",
        "secret": False,
        "choices": ["outbox", "smtp"],
        "help": "Režim e-mailové komunikace"
    },
    {
        "key": "EMAIL_FROM",
        "label": "Odesílatel e-mailu",
        "group": "E-mail (SMTP)",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "E-mailová adresa odesílatele"
    },
    {
        "key": "SMTP_HOST",
        "label": "SMTP server",
        "group": "E-mail (SMTP)",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "Adresa SMTP serveru"
    },
    {
        "key": "SMTP_PORT",
        "label": "SMTP port",
        "group": "E-mail (SMTP)",
        "type": "int",
        "secret": False,
        "choices": [],
        "help": "Port SMTP serveru"
    },
    {
        "key": "SMTP_USER",
        "label": "SMTP uživatelské jméno",
        "group": "E-mail (SMTP)",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "Uživatelské jméno pro SMTP"
    },
    {
        "key": "SMTP_PASSWORD",
        "label": "SMTP heslo",
        "group": "E-mail (SMTP)",
        "type": "str",
        "secret": True,
        "choices": [],
        "help": "Heslo pro SMTP"
    },
    {
        "key": "SMTP_STARTTLS",
        "label": "Použít STARTTLS",
        "group": "E-mail (SMTP)",
        "type": "bool",
        "secret": False,
        "choices": [],
        "help": "Použít STARTTLS pro zabezpečení spojení"
    },
    {
        "key": "DRUPAL_URL",
        "label": "URL Drupal systému",
        "group": "HR synchronizace (Drupal)",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "Adresa Drupal systému pro synchronizaci"
    },
    {
        "key": "DRUPAL_AUTH_MODE",
        "label": "Režim autentizace Drupal",
        "group": "HR synchronizace (Drupal)",
        "type": "choice",
        "secret": False,
        "choices": ["none", "basic", "token"],
        "help": "Režim autentizace pro přístup k Drupal systému"
    },
    {
        "key": "DRUPAL_USER",
        "label": "Uživatelské jméno Drupal",
        "group": "HR synchronizace (Drupal)",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "Uživatelské jméno pro přístup k Drupal systému"
    },
    {
        "key": "DRUPAL_PASSWORD",
        "label": "Heslo Drupal",
        "group": "HR synchronizace (Drupal)",
        "type": "str",
        "secret": True,
        "choices": [],
        "help": "Heslo pro přístup k Drupal systému"
    },
    {
        "key": "DRUPAL_TOKEN",
        "label": "Přístupový token Drupal",
        "group": "HR synchronizace (Drupal)",
        "type": "str",
        "secret": True,
        "choices": [],
        "help": "Přístupový token pro přístup k Drupal systému"
    },
    {
        "key": "DRUPAL_FIELD_MAP",
        "label": "Mapování polí Drupal",
        "group": "HR synchronizace (Drupal)",
        "type": "json",
        "secret": False,
        "choices": [],
        "help": "Mapování polí pro synchronizaci s Drupal systémem"
    },
    {
        "key": "DRUPAL_FILTER",
        "label": "Filtr pro Drupal",
        "group": "HR synchronizace (Drupal)",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "Filtr pro filtrování dat při synchronizaci s Drupal systémem"
    }
]


class SettingsService:
    MASK = '••••••••'

    def __init__(self, repo: 'SettingsRepository'):
        self.repo = repo

    def effective(self, base: Dict[str, Any]) -> Dict[str, Any]:
        """Copy of base with every stored setting applied, coerced by type."""
        result = base.copy()
        
        # Get all stored settings
        stored_settings = self.repo.all()
        
        for setting_def in SETTINGS_SCHEMA:
            key = setting_def['key']
            if key in stored_settings:
                value = stored_settings[key]
                
                # Apply type coercion
                if setting_def['type'] == 'int':
                    try:
                        result[key] = int(value)
                    except ValueError:
                        # If conversion fails, keep original value
                        result[key] = value
                elif setting_def['type'] == 'bool':
                    # Convert string to boolean (case insensitive)
                    result[key] = value.lower() in ('1', 'true', 'yes', 'on')
                elif setting_def['type'] == 'json':
                    # Keep JSON as string (raw text)
                    result[key] = value
                else:
                    # For str, choice, text types - keep as string
                    result[key] = value
        
        return result

    def save(self, values: Dict[str, Any], updated_by: str) -> None:
        """Save settings to repository."""
        for setting_def in SETTINGS_SCHEMA:
            key = setting_def['key']
            if key in values:
                value = values[key]
                
                # Handle secret fields
                if setting_def['secret'] and value == self.MASK:
                    # Skip saving if it's a masked secret
                    continue
                
                # Handle empty values - delete the setting
                if value == '':
                    self.repo.delete(key)
                else:
                    # Save the setting
                    self.repo.set(key, str(value), updated_by)

    def validate(self, values: Dict[str, Any]) -> List[str]:
        """Validate settings and return list of problems."""
        problems = []
        
        for setting_def in SETTINGS_SCHEMA:
            key = setting_def['key']
            if key not in values:
                continue
                
            value = values[key]
            
            # Skip validation for empty values (they will be deleted)
            if value == '':
                continue
                
            # Validate based on type
            if setting_def['type'] == 'int':
                try:
                    int_value = int(value)
                    if key in ['HANDOVER_TOKEN_HOURS', 'SMTP_PORT']:
                        if int_value <= 0:
                            problems.append(f"{key}: Musí být větší než 0")
                except ValueError:
                    problems.append(f"{key}: Musí být celé číslo")
                    
            elif setting_def['type'] == 'choice':
                if value not in setting_def['choices']:
                    problems.append(f"{key}: Neplatná volba")
                    
            elif setting_def['type'] == 'json':
                try:
                    json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    problems.append(f"{key}: Musí být platný JSON objekt")
        
        return problems

    def for_form(self, base: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Prepare settings for form display."""
        result = []
        
        # Get all stored settings
        stored_settings = self.repo.all()
        
        for setting_def in SETTINGS_SCHEMA:
            key = setting_def['key']
            
            # Prepare the value for display
            if setting_def['secret'] and key in stored_settings:
                # For secret fields with stored values, show masked value
                value = self.MASK
            elif key in stored_settings:
                # For non-secret fields with stored values, show the actual value
                value = stored_settings[key]
            else:
                # For fields not yet set, use base value or empty string
                value = str(base.get(key, ''))
                
            # Create the form item
            item = {
                'key': key,
                'label': setting_def['label'],
                'group': setting_def['group'],
                'type': setting_def['type'],
                'secret': setting_def['secret'],
                'choices': setting_def['choices'],
                'help': setting_def['help'],
                'value': value
            }
            
            result.append(item)
            
        return result