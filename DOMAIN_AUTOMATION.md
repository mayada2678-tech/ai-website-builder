# Automated domain provisioning

The production flow is:

1. Streamlit checks the requested domain directly with INWX.
2. Streamlit deploys an unbound preview to Vercel.
3. Stripe Checkout receives the normalized domain and Vercel project ID as server-side metadata.
4. Stripe calls `POST /api/stripe_webhook` after payment.
5. The webhook verifies the raw request body and `Stripe-Signature`.
6. INWX registers the domain and creates the Vercel DNS records.
7. The webhook assigns the domain to the Vercel project.

## Streamlit secrets

Add these values to `.streamlit/secrets.toml` or the Streamlit deployment secrets:

```toml
stripe_secret_key = "sk_test_..."
stripe_price_id = "price_..."
stripe_success_url = "https://your-builder.streamlit.app"

inwx_username = "..."
inwx_password = "..."
inwx_environment = "ote"
```

`inwx_environment = "ote"` is the safe default. The public RDAP/MCP result is never allowed to enable purchasing; only a successful INWX check enables Checkout.

## Webhook deployment variables

Deploy this repository as a separate Vercel project for the webhook and configure:

```text
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
INWX_USERNAME=...
INWX_PASSWORD=...
INWX_ENVIRONMENT=ote
INWX_REGISTRANT_HANDLE=...
INWX_ADMIN_HANDLE=...
INWX_TECH_HANDLE=...
INWX_BILLING_HANDLE=...
VERCEL_TOKEN=...
VERCEL_APEX_IP=76.76.21.21
VERCEL_CNAME_TARGET=cname.vercel-dns.com
```

Register this Stripe endpoint:

```text
https://website-domain-webhook.vercel.app/api/stripe_webhook
```

The Stripe test endpoint is registered as `we_1UElXKRiHK1kZVcgwSrF3EfK`.
Its signing secret is stored as an encrypted Vercel environment variable and
must not be copied into source control.

Subscribe to:

- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`

Use the signing secret belonging to this exact Dashboard webhook endpoint. Stripe CLI webhook secrets are different.

The deployed webhook project still requires these INWX OTE values before an
end-to-end test purchase can provision a domain:

```text
INWX_USERNAME
INWX_PASSWORD
INWX_REGISTRANT_HANDLE
INWX_ADMIN_HANDLE
INWX_TECH_HANDLE
INWX_BILLING_HANDLE
```

## Live activation

Complete the entire checkout and provisioning flow in Stripe test mode and INWX OTE first. For production, change `INWX_ENVIRONMENT` to `live` and add:

```text
INWX_LIVE_PURCHASE=true
```

Without this explicit switch, `domain.create` is rejected in the live environment. Keep all registrar and Stripe credentials server-side. Never put them in generated customer HTML or browser JavaScript.

Before enabling live purchases, verify the current DNS targets in the Vercel project documentation and override `VERCEL_APEX_IP` or `VERCEL_CNAME_TARGET` if Vercel specifies different values.
