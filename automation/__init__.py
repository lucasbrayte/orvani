"""Automação segura do catálogo de afiliados da Orvani."""

__all__ = ("build_parser", "main", "validate_environment")


def __getattr__(name: str):
    if name in __all__:
        from .cli import build_parser, main, validate_environment

        return {
            "build_parser": build_parser,
            "main": main,
            "validate_environment": validate_environment,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
