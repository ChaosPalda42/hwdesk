from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from src.config import HANDOVER_STATUSES
from src.services.tokens import HandoverTokens
from src.services.protocol_pdf import render_protocol_pdf


class HandoverError(ValueError):
    """Custom exception for handover service errors."""
    pass


class HandoverService:
    def __init__(
        self,
        handovers: Any,
        assignments: Any,
        assets: Any,
        employees: Any,
        audit: Any,
        email: Any,
        tokens: HandoverTokens,
        base_url: str,
        company: str,
        protocol_dir: str,
        copy_to: str = "",
    ):
        self.handovers = handovers
        self.assignments = assignments
        self.assets = assets
        self.employees = employees
        self.audit = audit
        self.email = email
        self.tokens = tokens
        self.base_url = base_url
        self.company = company
        self.protocol_dir = protocol_dir
        self.copy_to = copy_to.lower()

    def start_handover(
        self, actor: str, asset_id: int, employee_id: int, note: str = ""
    ) -> dict:
        # Validate asset exists and is in stock
        asset = self.assets.get(asset_id)
        if not asset:
            raise HandoverError("Asset does not exist")
        if asset["status"] != "in_stock":
            raise HandoverError("Asset is not in stock")

        # Validate employee exists and is active
        employee = self.employees.get(employee_id)
        if not employee:
            raise HandoverError("Employee does not exist")
        if not employee["active"]:
            raise HandoverError("Employee is not active")

        # Create handover record
        now = datetime.now(timezone.utc)
        year = now.year
        protocol_number = self.handovers.next_protocol_number(year)
        
        handover = self.handovers.create(
            kind="handover",
            asset_id=asset_id,
            employee_id=employee_id,
            created_by=actor,
            protocol_number=protocol_number,
            note=note,
        )

        # Update asset status to pending_handover
        self.assets.set_status(asset_id, "pending_handover")

        # Generate token for confirmation
        token = self.tokens.issue(handover["id"], employee["email"])

        # Prepare email content
        asset_tag = asset["asset_tag"]
        brand = asset["brand"]
        model = asset["model"]
        serial_number = asset["serial_number"]
        
        subject = f"Potvrzení převzetí zařízení {asset_tag}"
        
        # Create email content (text and HTML)
        text_content = f"""
Potvrzení převzetí zařízení

Zařízení:
- Inventární číslo: {asset_tag}
- Značka: {brand}
- Model: {model}
- Sériové číslo: {serial_number}

Poznámka: {note}

Pro potvrzení převzetí zařízení klikněte na následující odkaz:
{self.base_url}/handovers/confirm/{token}

Děkujeme.
"""
        
        html_content = f"""
<html>
<body>
<h3>Potvrzení převzetí zařízení</h3>

<p>Zařízení:</p>
<ul>
<li>Inventární číslo: {asset_tag}</li>
<li>Značka: {brand}</li>
<li>Model: {model}</li>
<li>Sériové číslo: {serial_number}</li>
</ul>

<p>Poznámka: {note}</p>

<p>Pro potvrzení převzetí zařízení klikněte na následující odkaz:</p>
<p><a href="{self.base_url}/handovers/confirm/{token}">{self.base_url}/handovers/confirm/{token}</a></p>

<p>Děkujeme.</p>
</body>
</html>
"""

        # Send email
        self.email.send(
            to=employee["email"],
            subject=subject,
            text=text_content,
            html=html_content,
        )

        # Mark handover as sent
        self.handovers.mark_sent(handover["id"])

        # Audit the action
        self.audit.record(
            actor=actor,
            action="handover.started",
            entity="handover",
            entity_id=handover["id"],
            details={"handover_id": handover["id"], "asset_id": asset_id, "employee_id": employee_id},
        )

        return handover

    def start_return(self, actor: str, asset_id: int, note: str = "") -> dict:
        # Find open assignment for the asset
        assignment = self.assignments.get_open_for_asset(asset_id)
        if not assignment:
            raise HandoverError("No open assignment found for this asset")

        # Get employee from the assignment
        employee = self.employees.get(assignment["employee_id"])
        if not employee:
            raise HandoverError("Employee does not exist")

        # Create handover record
        now = datetime.now(timezone.utc)
        year = now.year
        protocol_number = self.handovers.next_protocol_number(year)
        
        handover = self.handovers.create(
            kind="return",
            asset_id=asset_id,
            employee_id=assignment["employee_id"],
            created_by=actor,
            protocol_number=protocol_number,
            note=note,
        )

        # Update asset status to pending_return
        self.assets.set_status(asset_id, "pending_return")

        # Generate token for confirmation
        token = self.tokens.issue(handover["id"], employee["email"])

        # Prepare email content
        asset_tag = self.assets.get(asset_id)["asset_tag"]
        
        subject = f"Potvrzení vrácení zařízení {asset_tag}"
        
        # Create email content (text and HTML)
        text_content = f"""
Potvrzení vrácení zařízení

Zařízení:
- Inventární číslo: {asset_tag}

Poznámka: {note}

Pro potvrzení vrácení zařízení klikněte na následující odkaz:
{self.base_url}/handovers/confirm/{token}

Děkujeme.
"""
        
        html_content = f"""
<html>
<body>
<h3>Potvrzení vrácení zařízení</h3>

<p>Zařízení:</p>
<ul>
<li>Inventární číslo: {asset_tag}</li>
</ul>

<p>Poznámka: {note}</p>

<p>Pro potvrzení vrácení zařízení klikněte na následující odkaz:</p>
<p><a href="{self.base_url}/handovers/confirm/{token}">{self.base_url}/handovers/confirm/{token}</a></p>

<p>Děkujeme.</p>
</body>
</html>
"""

        # Send email
        self.email.send(
            to=employee["email"],
            subject=subject,
            text=text_content,
            html=html_content,
        )

        # Mark handover as sent
        self.handovers.mark_sent(handover["id"])

        # Audit the action
        self.audit.record(
            actor=actor,
            action="return.started",
            entity="handover",
            entity_id=handover["id"],
            details={"handover_id": handover["id"], "asset_id": asset_id, "employee_id": assignment["employee_id"]},
        )

        return handover

    def request_return(self, employee_email: str, asset_id: int, note: str = "") -> dict:
        # Find open assignment for the asset
        assignment = self.assignments.get_open_for_asset(asset_id)
        if not assignment:
            raise HandoverError("No open assignment found for this asset")

        # Validate that the employee is the holder of the open assignment
        employee = self.employees.get_by_email(employee_email)
        if not employee:
            raise HandoverError("Employee does not exist")
        if employee["id"] != assignment["employee_id"]:
            raise HandoverError("Employee is not the holder of the open assignment")

        # Create handover record
        now = datetime.now(timezone.utc)
        year = now.year
        protocol_number = self.handovers.next_protocol_number(year)
        
        handover = self.handovers.create(
            kind="return",
            asset_id=asset_id,
            employee_id=assignment["employee_id"],
            created_by=employee_email,
            protocol_number=protocol_number,
            note=note,
        )

        # Update asset status to pending_return
        self.assets.set_status(asset_id, "pending_return")

        # Generate token for confirmation
        token = self.tokens.issue(handover["id"], employee["email"])

        # Prepare email content
        asset_tag = self.assets.get(asset_id)["asset_tag"]
        
        subject = f"Potvrzení vrácení zařízení {asset_tag}"
        
        # Create email content (text and HTML)
        text_content = f"""
Potvrzení vrácení zařízení

Zařízení:
- Inventární číslo: {asset_tag}

Poznámka: {note}

Pro potvrzení vrácení zařízení klikněte na následující odkaz:
{self.base_url}/handovers/confirm/{token}

Děkujeme.
"""
        
        html_content = f"""
<html>
<body>
<h3>Potvrzení vrácení zařízení</h3>

<p>Zařízení:</p>
<ul>
<li>Inventární číslo: {asset_tag}</li>
</ul>

<p>Poznámka: {note}</p>

<p>Pro potvrzení vrácení zařízení klikněte na následující odkaz:</p>
<p><a href="{self.base_url}/handovers/confirm/{token}">{self.base_url}/handovers/confirm/{token}</a></p>

<p>Děkujeme.</p>
</body>
</html>
"""

        # Send email
        self.email.send(
            to=employee["email"],
            subject=subject,
            text=text_content,
            html=html_content,
        )

        # Mark handover as sent
        self.handovers.mark_sent(handover["id"])

        # Audit the action
        self.audit.record(
            actor=employee_email,
            action="return.started",
            entity="handover",
            entity_id=handover["id"],
            details={"handover_id": handover["id"], "asset_id": asset_id, "employee_id": assignment["employee_id"]},
        )

        return handover

    def confirm(self, token: str, actor_email: str) -> dict:
        # Verify the token
        token_data = self.tokens.verify(token)
        if not token_data:
            raise HandoverError("Invalid or expired token")

        # Get the handover record
        handover = self.handovers.get(token_data["handover_id"])
        if not handover:
            raise HandoverError("Handover does not exist")

        # Check that the handover is still pending
        if handover["status"] != "pending":
            raise HandoverError("Handover is not pending")

        # Validate that the actor email matches the token email and employee email
        if actor_email.lower() != token_data["email"].lower():
            raise HandoverError("Actor email does not match token email")

        # Get employee and asset details
        employee = self.employees.get(handover["employee_id"])
        if not employee:
            raise HandoverError("Employee does not exist")

        asset = self.assets.get(handover["asset_id"])
        if not asset:
            raise HandoverError("Asset does not exist")

        # Process based on handover kind
        if handover["kind"] == "handover":
            # Open an assignment for the employee
            self.assignments.open(
                asset_id=handover["asset_id"],
                employee_id=handover["employee_id"],
                handover_id=handover["id"]
            )

            # Update asset status to assigned
            self.assets.set_status(handover["asset_id"], "assigned")

        elif handover["kind"] == "return":
            # Close the open assignment with return_id
            assignment = self.assignments.get_open_for_asset(handover["asset_id"])
            if not assignment:
                raise HandoverError("No open assignment found for this asset")
            
            self.assignments.close(assignment["id"], handover["id"])

            # Update asset status to in_stock
            self.assets.set_status(handover["asset_id"], "in_stock")

        # Render the PDF protocol
        now = datetime.now(timezone.utc).isoformat()
        protocol_path = f"{self.protocol_dir}/{handover['protocol_number']}.pdf"
        
        render_protocol_pdf(
            path=protocol_path,
            protocol_number=handover["protocol_number"],
            kind=handover["kind"],
            company=self.company,
            employee=employee,
            asset=asset,
            created_by=handover["created_by"],
            confirmed_at=now,
            note=handover["note"]
        )

        # Update handover status to confirmed
        self.handovers.set_status(
            id=handover["id"],
            status="confirmed",
            confirmed_at=now,
            protocol_path=protocol_path
        )

        # Send the PDF to both employee and created_by
        with open(protocol_path, "rb") as pdf_file:
            pdf_content = pdf_file.read()
        
        kind_word = 'převzetí' if handover['kind'] == 'handover' else 'vrácení'
        subject = f"Protokol {handover['protocol_number']} — {kind_word} zařízení {asset['asset_tag']}"
        text = (
            f"{kind_word.capitalize()} zařízení {asset['asset_tag']} ({asset['brand']} {asset['model']}) "
            f"bylo potvrzeno. Protokol {handover['protocol_number']} je v příloze."
        )
        # The employee always; the person who started it when that is an
        # e-mail (an API key is not); and the configured copy address.
        recipients = [employee["email"].lower()]
        for candidate in (handover["created_by"].lower(), self.copy_to):
            if candidate and "@" in candidate and candidate not in recipients:
                recipients.append(candidate)
        for recipient in recipients:
            self.email.send(
                to=recipient,
                subject=subject,
                text=text,
                html=f"<p>{text}</p>",
                attachments=[(f"{handover['protocol_number']}.pdf", pdf_content, "application/pdf")],
            )

        # Audit the action
        self.audit.record(
            actor=actor_email,
            action="handover.confirmed",
            entity="handover",
            entity_id=handover["id"],
            details={"handover_id": handover["id"], "asset_id": handover["asset_id"]},
        )

        return self.handovers.get(handover["id"])

    def decline(self, token: str, actor_email: str, reason: str = "") -> dict:
        # Verify the token
        token_data = self.tokens.verify(token)
        if not token_data:
            raise HandoverError("Invalid or expired token")

        # Get the handover record
        handover = self.handovers.get(token_data["handover_id"])
        if not handover:
            raise HandoverError("Handover does not exist")

        # Check that the handover is still pending
        if handover["status"] != "pending":
            raise HandoverError("Handover is not pending")

        # Validate that the actor email matches the token email and employee email
        if actor_email.lower() != token_data["email"].lower():
            raise HandoverError("Actor email does not match token email")

        # Update handover status to declined
        self.handovers.set_status(
            id=handover["id"],
            status="declined",
            decline_reason=reason
        )

        # Reset asset status based on handover kind
        if handover["kind"] == "handover":
            # Asset back to in_stock for handover
            self.assets.set_status(handover["asset_id"], "in_stock")
        elif handover["kind"] == "return":
            # Asset back to assigned for return
            self.assets.set_status(handover["asset_id"], "assigned")

        # Audit the action
        self.audit.record(
            actor=actor_email,
            action="handover.declined",
            entity="handover",
            entity_id=handover["id"],
            details={"handover_id": handover["id"], "asset_id": handover["asset_id"], "reason": reason},
        )

        return self.handovers.get(handover["id"])

    def cancel(self, actor: str, handover_id: int) -> dict:
        # Get the handover record
        handover = self.handovers.get(handover_id)
        if not handover:
            raise HandoverError("Handover does not exist")

        # Check that the handover is still pending
        if handover["status"] != "pending":
            raise HandoverError("Handover is not pending")

        # Update handover status to cancelled
        self.handovers.set_status(
            id=handover_id,
            status="cancelled"
        )

        # Reset asset status based on handover kind
        if handover["kind"] == "handover":
            # Asset back to in_stock for handover
            self.assets.set_status(handover["asset_id"], "in_stock")
        elif handover["kind"] == "return":
            # Asset back to assigned for return
            self.assets.set_status(handover["asset_id"], "assigned")

        # Audit the action
        self.audit.record(
            actor=actor,
            action="handover.cancelled",
            entity="handover",
            entity_id=handover["id"],
            details={"handover_id": handover["id"], "asset_id": handover["asset_id"]},
        )

        # Return the updated handover
        return self.handovers.get(handover["id"])

    def overview_for_employee(self, employee_id: int) -> dict:
        # Get assigned assets (open assignments)
        open_assignments = self.assignments.list_open_for_employee(employee_id)
        
        assigned_list = []
        for assignment in open_assignments:
            asset = self.assets.get(assignment["asset_id"])
            if asset:
                # Find the handover record for this assignment
                handovers_for_asset = self.handovers.list_for_asset(assignment["asset_id"])
                handover = None
                for h in handovers_for_asset:
                    if h["employee_id"] == employee_id and h["status"] == "confirmed":
                        handover = h
                        break
                
                # Add asset details to the handover for the assigned list
                if handover:
                    assigned_list.append({
                        "assignment": assignment,
                        "asset": asset,
                        "handover": handover
                    })

        # Get pending handovers for this employee
        pending_handovers = self.handovers.list_pending_for_employee(employee_id)
        
        # Add asset details to pending handovers
        pending_with_assets = []
        for handover in pending_handovers:
            asset = self.assets.get(handover["asset_id"])
            if asset:
                # Create a copy of the handover with added asset info
                handover_with_asset = dict(handover)
                handover_with_asset["asset"] = asset
                pending_with_assets.append(handover_with_asset)

        # Get all handover history for this employee (newest first)
        history = self.handovers.list_for_employee(employee_id)

        return {
            "assigned": assigned_list,
            "pending": pending_with_assets,
            "history": history
        }

    def expire_stale(self, older_than_hours: int) -> int:
        # Get all pending handovers
        pending_handovers = self.handovers.list_all(status="pending")
        
        count = 0
        now = datetime.now(timezone.utc)
        
        for handover in pending_handovers:
            # Calculate the time difference
            created_at = datetime.fromisoformat(handover["created_at"])
            # Ensure created_at is timezone-aware for comparison
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            diff_hours = (now - created_at).total_seconds() / 3600
            
            if diff_hours > older_than_hours:
                # Expire this handover
                self.handovers.set_status(
                    id=handover["id"],
                    status="expired"
                )
                
                # Reset asset status based on handover kind
                if handover["kind"] == "handover":
                    # Asset back to in_stock for handover
                    self.assets.set_status(handover["asset_id"], "in_stock")
                elif handover["kind"] == "return":
                    # Asset back to assigned for return
                    self.assets.set_status(handover["asset_id"], "assigned")
                
                count += 1

        return count

    def with_details(self, handover: dict) -> dict:
        # Add asset and employee details to the handover
        asset = self.assets.get(handover["asset_id"])
        employee = self.employees.get(handover["employee_id"])
        
        return {
            **handover,
            "asset": asset,
            "employee": employee
        }