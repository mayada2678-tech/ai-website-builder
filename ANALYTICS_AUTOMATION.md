# Analytics and AI optimization

## Supabase setup

1. Create a Supabase project.
2. Open the SQL editor and execute `supabase_schema.sql`. Run it again after
   updates; its migrations use `if not exists` and are safe to repeat.
3. Add these values to local and deployed Streamlit secrets:

```toml
supabase_url = "https://YOUR_PROJECT.supabase.co"
supabase_service_role_key = "YOUR_SERVICE_ROLE_KEY"
```

Never expose the service-role key in generated HTML. During publishing, Streamlit
stores it as an encrypted Vercel environment variable. Browser events are sent to
the generated `/api/analytics` serverless route, which writes to Supabase.

## Collected data

Tracking starts only after the visitor accepts the analytics prompt. It stores:

- a random session UUID in `sessionStorage`
- device category (`mobile`, `tablet`, or `desktop`)
- a short label for clicked links and buttons
- whether the click was a contact or submit conversion
- session duration and maximum scroll depth

The script does not store names, email addresses, form contents, IP addresses, or
browser fingerprints. Supabase tables have Row Level Security enabled and are only
accessed with the server-side service-role key.

## Optimization workflow

The admin account configured through `support_admin_email` sees **KI-Optimierung
und A/B-Test** in the customer-service tab.

1. Publish the site once to install the analytics route and tracking script.
2. Wait until at least 500 unique sessions have opted in.
3. Run **Analytics auswerten und Testversion erstellen**.
4. The app aggregates the events and sends only the summary plus current HTML to
   OpenAI.
5. The generated candidate is validated, stored in `site_versions` with status
   `testing`, and loaded into the Streamlit preview.
6. After the next regular Vercel publication, consenting browser sessions are
   deterministically assigned to A or B. A stays on the live HTML. B requests the
   latest `testing` HTML through the server-side `/api/variant` route.
7. Analytics rows include `version` and `event_type`, so conversions can be
   compared without exposing Supabase credentials to the browser.
8. Review the result before promoting a candidate. A regular publication archives
   previous `live` rows and stores the published HTML as `live`.

The split starts only after analytics consent. It uses `sessionStorage`, so one
browser tab remains on the same variant for its session. If no testing version is
available, B assignments fall back to A without showing an error page. This
application-level split is suitable for the initial experiment; Vercel Edge
Middleware remains preferable later for redirect-free routing at larger scale.

## Cron automation

The optimization logic is exposed through `create_analytics_optimized_version()`
in `app.py`. A future authenticated cron endpoint can call the same workflow. Do not
expose that operation publicly without a signed request, rate limiting, version
locking, and rollback support.