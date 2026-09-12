"""Vercel Python Function for verified Stripe domain-provisioning events."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
import json
import os

import stripe

from domain_provisioning import ProvisioningError, provision_paid_domain


SUPPORTED_EVENTS = {
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
}


class handler(BaseHTTPRequestHandler):
    def _json_response(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
        if not webhook_secret or not stripe.api_key:
            self._json_response(503, {"error": "Webhook secrets are not configured."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            signature = self.headers.get("Stripe-Signature", "")
            event = stripe.Webhook.construct_event(raw_body, signature, webhook_secret)
        except (ValueError, stripe.error.SignatureVerificationError):
            self._json_response(400, {"error": "Invalid Stripe webhook signature."})
            return

        if event["type"] not in SUPPORTED_EVENTS:
            self._json_response(200, {"received": True, "ignored": True})
            return

        event_session = event["data"]["object"]
        if event_session.get("payment_status") != "paid":
            self._json_response(200, {"received": True, "waiting_for_payment": True})
            return

        checkout_session = stripe.checkout.Session.retrieve(event_session["id"])
        metadata = dict(checkout_session.get("metadata") or {})
        if metadata.get("provisioning_status") in {"processing", "complete"}:
            self._json_response(200, {"received": True, "duplicate": True})
            return

        domain = metadata.get("domain", "")
        project_id = metadata.get("vercel_project_id", "")
        if not domain or not project_id:
            self._json_response(422, {"error": "Checkout is missing provisioning metadata."})
            return

        try:
            stripe.checkout.Session.modify(
                checkout_session["id"],
                metadata={**metadata, "provisioning_status": "processing"},
            )
            result = provision_paid_domain(domain, project_id)
            stripe.checkout.Session.modify(
                checkout_session["id"],
                metadata={
                    **metadata,
                    "provisioning_status": "complete",
                    "provisioned_domain": result["domain"],
                    "registrar_environment": result["environment"],
                },
            )
        except (ProvisioningError, stripe.error.StripeError, OSError) as error:
            stripe.checkout.Session.modify(
                checkout_session["id"],
                metadata={
                    **metadata,
                    "provisioning_status": "failed",
                    "provisioning_error": str(error)[:450],
                },
            )
            self._json_response(500, {"error": "Domain provisioning failed."})
            return

        self._json_response(200, {"received": True, "domain": result["domain"]})
