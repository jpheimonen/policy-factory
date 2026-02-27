"""Prompt loader for Policy Factory.

Loads prompts from markdown files with template variable substitution.
Adapted from cc-runner's PromptLoader with identical API.
"""

from pathlib import Path


class PromptLoader:
    """Load prompts from files with template variable substitution."""

    def __init__(self, prompts_dir: Path | str | None = None):
        """Initialize with prompts directory.

        Args:
            prompts_dir: Path to prompts directory. Defaults to
                         ``src/policy_factory/prompts/`` relative to
                         this package.
        """
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent
        self.prompts_dir = Path(prompts_dir)

    def load(self, category: str, name: str, **variables: str) -> str:
        """Load a prompt file and substitute variables.

        Args:
            category: Subdirectory (e.g., ``"generators"``, ``"critics"``).
            name: Prompt file name without extension.
            **variables: Template variables to substitute.

        Returns:
            Prompt content with variables substituted.

        Raises:
            FileNotFoundError: If prompt file doesn't exist.
        """
        path = self.prompts_dir / category / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(
                f"Prompt not found: {path}\nExpected: prompts/{category}/{name}.md"
            )

        content = path.read_text()

        # Substitute variables using str.format()
        # Double braces {{ }} are escaped and become literal { }
        if variables:
            content = content.format(**variables)

        return content

    def load_section(self, name: str) -> str:
        """Load a single section file from ``prompts/sections/``.

        Sections are static preambles — no variable substitution is
        applied.

        Args:
            name: Section name (file name without ``.md`` extension).

        Returns:
            Section content as a string.

        Raises:
            FileNotFoundError: If section file doesn't exist.
        """
        section_file = self.prompts_dir / "sections" / f"{name}.md"
        if not section_file.exists():
            raise FileNotFoundError(
                f"Prompt section not found: {section_file}\n"
                f"Expected: prompts/sections/{name}.md"
            )
        return section_file.read_text()

    def load_sections(self, names: list[str]) -> str:
        """Load multiple sections and concatenate them.

        Args:
            names: List of section names to load.

        Returns:
            Concatenated section content joined with double newlines,
            or an empty string for an empty list.

        Raises:
            FileNotFoundError: If any section file doesn't exist.
        """
        if not names:
            return ""
        return "\n\n".join(self.load_section(name) for name in names)


# Module-level singleton for convenience
_default_loader: PromptLoader | None = None


def get_prompt_loader() -> PromptLoader:
    """Get the default prompt loader singleton."""
    global _default_loader
    if _default_loader is None:
        _default_loader = PromptLoader()
    return _default_loader


def load_prompt(category: str, name: str, **variables: str) -> str:
    """Convenience function to load a prompt using the default loader.

    Args:
        category: Subdirectory (e.g., ``"generators"``, ``"critics"``).
        name: Prompt file name without extension.
        **variables: Template variables to substitute.

    Returns:
        Prompt content with variables substituted.
    """
    return get_prompt_loader().load(category, name, **variables)


def load_section(name: str) -> str:
    """Load a single prompt section by name.

    Args:
        name: Section name (file name without ``.md`` extension).

    Returns:
        Section content as a string.

    Raises:
        FileNotFoundError: If section file doesn't exist.
    """
    return get_prompt_loader().load_section(name)


def load_sections(names: list[str]) -> str:
    """Load multiple prompt sections and concatenate them.

    Args:
        names: List of section names to load.

    Returns:
        Concatenated section content, or empty string if names is empty.

    Raises:
        FileNotFoundError: If any section file doesn't exist.
    """
    return get_prompt_loader().load_sections(names)
