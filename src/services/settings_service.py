import json
import sqlite3
from typing import Optional, List, Dict, Any


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
        "label": "Režim e-mailu",
        "group": "E-mail (SMTP)",
        "type": "choice",
        "secret": False,
        "choices": ["outbox", "smtp"],
        "help": "Režim odesílání e-mailů"
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
        "label": "SMTP hostitel",
        "group": "E-mail (SMTP)",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "SMTP server hostitel"
    },
    {
        "key": "SMTP_PORT",
        "label": "SMTP port",
        "group": "E-mail (SMTP)",
        "type": "int",
        "secret": False,
        "choices": [],
        "help": "SMTP server port"
    },
    {
        "key": "SMTP_USER",
        "label": "SMTP uživatel",
        "group": "E-mail (SMTP)",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "SMTP uživatelské jméno"
    },
    {
        "key": "SMTP_PASSWORD",
        "label": "SMTP heslo",
        "group": "E-mail (SMTP)",
        "type": "str",
        "secret": True,
        "choices": [],
        "help": "SMTP heslo"
    },
    {
        "key": "SMTP_STARTTLS",
        "label": "Použít STARTTLS",
        "group": "E-mail (SMTP)",
        "type": "bool",
        "secret": False,
        "choices": [],
        "help": "Povolit STARTTLS pro zabezpečené připojení"
    },
    {
        "key": "DRUPAL_URL",
        "label": "URL Drupal",
        "group": "HR synchronizace (Drupal)",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "URL adresa Drupal systému"
    },
    {
        "key": "DRUPAL_AUTH_MODE",
        "label": "Režim autentizace Drupal",
        "group": "HR synchronizace (Drupal)",
        "type": "choice",
        "secret": False,
        "choices": ["none", "basic", "token"],
        "help": "Režim autentizace pro Drupal"
    },
    {
        "key": "DRUPAL_USER",
        "label": "Uživatel Drupal",
        "group": "HR synchronizace (Drupal)",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "Uživatelské jméno pro přístup k Drupal"
    },
    {
        "key": "DRUPAL_PASSWORD",
        "label": "Heslo Drupal",
        "group": "HR synchronizace (Drupal)",
        "type": "str",
        "secret": True,
        "choices": [],
        "help": "Heslo pro přístup k Drupal"
    },
    {
        "key": "DRUPAL_TOKEN",
        "label": "Token Drupal",
        "group": "HR synchronizace (Drupal)",
        "type": "str",
        "secret": True,
        "choices": [],
        "help": "Autentizační token pro Drupal"
    },
    {
        "key": "DRUPAL_FIELD_MAP",
        "label": "Mapování polí Drupal",
        "group": "HR synchronizace (Drupal)",
        "type": "json",
        "secret": False,
        "choices": [],
        "help": "Mapování polí mezi systémy"
    },
    {
        "key": "DRUPAL_FILTER",
        "label": "Filtr Drupal",
        "group": "HR synchronizace (Drupal)",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "Filtr pro synchronizaci z Drupal"
    },
    {
        "key": "TAG_PREFIXES",
        "label": "Předpony štítků",
        "group": "Inventární čísla a štítky",
        "type": "json",
        "secret": False,
        "choices": [],
        "help": "Mapování typů majetku na předpony štítků"
    },
    {
        "key": "TAG_PAD",
        "label": "Délka štítku",
        "group": "Inventární čísla a štítky",
        "type": "int",
        "secret": False,
        "choices": [],
        "help": "Minimální délka štítku (přidání nul)"
    },
    {
        "key": "LABEL_PRINTER_HOST",
        "label": "Hostitel tiskárny štítků",
        "group": "Inventární čísla a štítky",
        "type": "str",
        "secret": False,
        "choices": [],
        "help": "IP adresa nebo název tiskárny štítků"
    },
    {
        "key": "LABEL_PRINTER_PORT",
        "label": "Port tiskárny štítků",
        "group": "Inventární čísla a štítky",
        "type": "int",
        "secret": False,
        "choices": [],
        "help": "Port tiskárny štítků"
    },
    {
        "key": "LABEL_ZPL_TEMPLATE",
        "label": "Šablona ZPL štítku",
        "group": "Inventární čísla a štítky",
        "type": "text",
        "secret": False,
        "choices": [],
        "help": "Šablona ZPL pro tisk štítků (placeholdery: {asset_tag} {brand} {model} {serial_number} {url} {company})"
    }
]


class SettingsService:
    MASK = '••••••••'

    def __init__(self, repo):
        self.repo = repo

    def effective(self, base: dict) -> dict:
        """Copy of base with every stored setting applied, coerced by type."""
        result = {}
        
        # Get all stored settings
        stored_settings = self.repo.all()
        
        # Process only the keys that exist in base or have stored values
        for setting_def in SETTINGS_SCHEMA:
            key = setting_def["key"]
            
            # Check if this key is in base or has a stored value
            if key in base or key in stored_settings:
                # Get the value - either from base or stored
                if key in stored_settings:
                    value = stored_settings[key]
                else:
                    value = base.get(key, '')
                
                # Apply type coercion
                if setting_def["type"] == "int":
                    try:
                        result[key] = int(value)
                    except (ValueError, TypeError):
                        # If conversion fails, keep the original value
                        result[key] = value
                elif setting_def["type"] == "bool":
                    # Convert string values to boolean (case insensitive)
                    if isinstance(value, str):
                        result[key] = value.lower() in ('1', 'true', 'yes', 'on')
                    else:
                        result[key] = bool(value)
                elif setting_def["type"] == "json":
                    # Keep JSON as string for now, validation will check it
                    result[key] = value
                else:
                    # For str, choice, text - just convert to string
                    result[key] = str(value)
        
        # Also ensure all base keys are in the result (they might not be in schema)
        for key, value in base.items():
            if key not in result:
                result[key] = value
        
        return result

    def save(self, values: dict, updated_by: str) -> None:
        """Save settings to repository."""
        stored_settings = self.repo.all()
        
        for setting_def in SETTINGS_SCHEMA:
            key = setting_def["key"]
            
            # Skip if key not in values
            if key not in values:
                continue
                
            value = values[key]
            
            # Handle secret fields with masking
            if setting_def["secret"] and value == self.MASK:
                # Skip saving if it's a masked secret (keep existing value)
                continue
            
            # Handle empty string - delete the setting
            if value == '':
                self.repo.delete(key)
            else:
                # Save the setting
                self.repo.set(key, str(value), updated_by)

    def validate(self, values: dict) -> List[str]:
        """Validate settings and return list of problems."""
        problems = []
        
        for setting_def in SETTINGS_SCHEMA:
            key = setting_def["key"]
            
            # Skip unknown keys
            if key not in values:
                continue
                
            value = values[key]
            
            # Validate based on type
            if setting_def["type"] == "int":
                try:
                    int_value = int(value)
                    # Validate that it's > 0 for specific fields
                    if key in ["HANDOVER_TOKEN_HOURS", "SMTP_PORT"] and int_value <= 0:
                        problems.append(f"{key}: Musí být větší než 0")
                except ValueError:
                    problems.append(f"{key}: Musí být platné číslo")
                    
            elif setting_def["type"] == "choice":
                if value not in setting_def["choices"]:
                    problems.append(f"{key}: Neplatná volba")
                    
            elif setting_def["type"] == "json":
                try:
                    json.loads(value)
                except json.JSONDecodeError:
                    problems.append(f"{key}: Musí být platný JSON")
                    
            # For other types, we don't validate specific constraints here
        
        return problems

    def for_form(self, base: dict) -> List[Dict]:
        """Prepare settings for form display."""
        result = []
        
        stored_settings = self.repo.all()
        
        for setting_def in SETTINGS_SCHEMA:
            key = setting_def["key"]
            value = stored_settings.get(key)
            
            # If it's a secret and we have a stored value, mask it
            if setting_def["secret"] and value is not None:
                display_value = self.MASK
            elif value is not None:
                # Use stored value
                display_value = value
            else:
                # Use base value or empty string
                display_value = str(base.get(key, ''))
            
            # Create form item
            form_item = {
                "key": key,
                "label": setting_def["label"],
                "group": setting_def["group"],
                "type": setting_def["type"],
                "secret": setting_def["secret"],
                "choices": setting_def["choices"],
                "help": setting_def["help"],
                "value": display_value
            }
            
            result.append(form_item)
            
        return result