from config import load_config, validate_config, ConfigError

try:
    cfg = load_config()

    print("Configuration loaded:")
    print(f"Repository : {cfg.repo}")
    print(f"KStars     : {cfg.kstars}")
    print(f"Dry run    : {cfg.dry_run}")
    print(f"Verbose    : {cfg.verbose}")

    print()
    print("Validating...")

    validate_config(cfg)

    print("Configuration is valid.")

except ConfigError as e:
    print(f"Configuration error:\n{e}")

