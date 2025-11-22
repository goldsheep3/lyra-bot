from typing import List, Optional


class HelpContent:
    def __init__(self, name: str, title: str, description: str, aliases: Optional[List[str]] = None):
        self.name: str = name
        self.title: str = title
        self.description: str = description
        self.contents: List[str] = []
        self.aliases: List[str] = aliases if aliases is not None else []
        self.superuser_contents: List[str] = []

    def add_alias(self, alias: str):
        self.aliases.append(alias)

    def add_content(self, command: str, content: str):
        self.contents.append(f"◎ {command}\n  {content}")

    def add_superuser_content(self, content: str):
        self.contents.append(f"◎ {content}")


class HelpContentsManager:
    def __init__(self):
        self.help_contents: dict[str, HelpContent] = {}

    def register_help_content(self, help_content: HelpContent):
        self.help_contents[help_content.name] = help_content
        for alias in help_content.aliases:
            self.help_contents[alias] = help_content

    def get_help_content(self, name: str) -> Optional[HelpContent]:
        return self.help_contents.get(name, None)

    def get_all_help_contents(self) -> List[HelpContent]:
        return list(self.help_contents.values())


lyra_helper = HelpContentsManager()
