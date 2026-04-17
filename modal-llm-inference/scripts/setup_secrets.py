"""
Setup Modal secrets for vLLM deployment
File: scripts/setup_secrets.py

Usage:
    python scripts/setup_secrets.py
"""

import os
import sys
import modal


def create_secret(name: str, env_vars: dict, overwrite: bool = False):
    """Create a Modal secret with environment variables.

    Args:
        name: Name of the secret
        env_vars: Dictionary of environment variable names and values
        overwrite: Whether to overwrite existing secret
    """
    print(f"\n{'=' * 60}")
    print(f"Creating secret: {name}")
    print(f"{'=' * 60}")

    # Check if secret already exists
    existing = None
    try:
        existing = modal.Secret.from_name(name)
        print(f"Secret '{name}' already exists.")
        if not overwrite:
            print("Skipping (use --overwrite to replace)")
            return existing
        print("Overwriting existing secret...")
    except modal.exception.NotFoundError:
        pass

    # Get values from environment
    secret_data = {}
    missing = []

    for var_name in env_vars:
        env_value = os.environ.get(var_name)

        if env_value:
            secret_data[var_name] = env_value
            print(f"  {var_name}: {env_value[:10]}...")
        else:
            # Try to get input
            value = input(f"  Enter {var_name} (or press Enter to skip): ")
            if value:
                secret_data[var_name] = value
            else:
                missing.append(var_name)

    if missing:
        print(f"\nWarning: Missing values for: {', '.join(missing)}")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return None

    if not secret_data:
        print("Error: No secret data provided")
        return None

    # Create secret
    try:
        secret = modal.Secret.from_dict(
            secret_name=name,
            **secret_data,
        )
        print(f"\nSecret '{name}' created successfully!")
        return secret
    except Exception as e:
        print(f"Error creating secret: {e}")
        return None


def main():
    """Setup all required secrets for vLLM deployment."""

    print("\n" + "=" * 60)
    print("Modal vLLM Secrets Setup")
    print("=" * 60)

    # Required secrets
    secrets_to_create = [
        {
            "name": "huggingface-secret",
            "description": "HuggingFace API token for model access",
            "env_vars": ["HF_TOKEN"],
        },
        {
            "name": "opencode-auth",
            "description": "OpenCode server authentication",
            "env_vars": ["OPENCODE_SERVER_PASSWORD"],
        },
        {
            "name": "tailscale-auth",
            "description": "Tailscale authentication for private networking",
            "env_vars": ["TAILSCALE_AUTHKEY"],
        },
    ]

    # Parse arguments
    overwrite = "--overwrite" in sys.argv

    # Create secrets
    created = []
    for secret_config in secrets_to_create:
        result = create_secret(
            name=secret_config["name"],
            env_vars=secret_config["env_vars"],
            overwrite=overwrite,
        )
        if result:
            created.append(secret_config["name"])

    # Summary
    print("\n" + "=" * 60)
    print("Setup Summary")
    print("=" * 60)
    print(f"Created: {len(created)} secrets")
    for name in created:
        print(f"  - {name}")

    # Instructions
    print("\n" + "=" * 60)
    print("Next Steps")
    print("=" * 60)
    print("""
1. Verify secrets in Modal dashboard:
   https://modal.com/settings/secrets

2. Test deployment:
   modal run examples/basic-deployment/gemma_server.py

3. Deploy to production:
   modal deploy examples/basic-deployment/gemma_server.py
    """)

    return 0 if len(created) > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
