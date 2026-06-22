"""Real upstream provider adapters (behind the gateway ``Provider`` ABC).

Each adapter translates the OpenAI-compatible wire models to/from a vendor API.
The provider SDKs are optional extras, lazy-imported only inside their own module
so the gateway (and CI) runs on the deterministic mock with no SDK installed.
"""
