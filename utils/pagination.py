"""
Reusable pagination view and category select for embeds.
"""

from __future__ import annotations

import discord
from discord.ui import View, Button, Select


class Paginator(View):
    """Simple Previous / Next paginator for a list of embeds."""

    def __init__(self, embeds: list[discord.Embed], author_id: int, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.author_id = author_id
        self.current = 0

        self.prev_button = Button(label="Previous", style=discord.ButtonStyle.secondary, disabled=True)
        self.next_button = Button(label="Next", style=discord.ButtonStyle.secondary, disabled=len(embeds) <= 1)
        self.page_button = Button(
            label=f"Page 1/{len(embeds)}",
            style=discord.ButtonStyle.primary,
            disabled=True,
        )

        self.prev_button.callback = self.go_previous
        self.next_button.callback = self.go_next

        self.add_item(self.prev_button)
        self.add_item(self.page_button)
        self.add_item(self.next_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the user who ran the command can control this menu.",
                ephemeral=True,
            )
            return False
        return True

    async def go_previous(self, interaction: discord.Interaction):
        self.current = max(0, self.current - 1)
        await self._update(interaction)

    async def go_next(self, interaction: discord.Interaction):
        self.current = min(len(self.embeds) - 1, self.current + 1)
        await self._update(interaction)

    async def _update(self, interaction: discord.Interaction):
        self.prev_button.disabled = self.current == 0
        self.next_button.disabled = self.current >= len(self.embeds) - 1
        self.page_button.label = f"Page {self.current + 1}/{len(self.embeds)}"
        await interaction.response.edit_message(embed=self.embeds[self.current], view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class CategorySelect(Select):
    def __init__(self, categories: dict[str, list[discord.Embed]], author_id: int):
        options = [
            discord.SelectOption(label=name, value=name)
            for name in categories.keys()
        ]
        super().__init__(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.categories = categories
        self.author_id = author_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the user who ran the command can control this menu.",
                ephemeral=True,
            )
            return

        chosen = self.values[0]
        embeds = self.categories.get(chosen, [])
        if not embeds:
            await interaction.response.send_message("No data for this category.", ephemeral=True)
            return

        # Replace the view with a paginator for the selected category
        view = CategoryView(self.categories, self.author_id, current_category=chosen)
        await interaction.response.edit_message(embed=embeds[0], view=view)


class CategoryView(View):
    """
    View that holds a category dropdown + optional pagination buttons.
    """

    def __init__(
        self,
        categories: dict[str, list[discord.Embed]],
        author_id: int,
        current_category: str | None = None,
        timeout: float = 180,
    ):
        super().__init__(timeout=timeout)
        self.categories = categories
        self.author_id = author_id
        self.current_category = current_category or next(iter(categories))
        self.current_page = 0

        # Dropdown
        self.add_item(CategorySelect(categories, author_id))

        embeds = categories[self.current_category]
        self.prev_button = Button(label="Previous", style=discord.ButtonStyle.secondary, disabled=True)
        self.next_button = Button(
            label="Next",
            style=discord.ButtonStyle.secondary,
            disabled=len(embeds) <= 1,
        )
        self.page_button = Button(
            label=f"Page 1/{len(embeds)}",
            style=discord.ButtonStyle.primary,
            disabled=True,
        )

        self.prev_button.callback = self.go_previous
        self.next_button.callback = self.go_next

        self.add_item(self.prev_button)
        self.add_item(self.page_button)
        self.add_item(self.next_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the user who ran the command can control this menu.",
                ephemeral=True,
            )
            return False
        return True

    async def go_previous(self, interaction: discord.Interaction):
        embeds = self.categories[self.current_category]
        self.current_page = max(0, self.current_page - 1)
        await self._update_page(interaction, embeds)

    async def go_next(self, interaction: discord.Interaction):
        embeds = self.categories[self.current_category]
        self.current_page = min(len(embeds) - 1, self.current_page + 1)
        await self._update_page(interaction, embeds)

    async def _update_page(self, interaction: discord.Interaction, embeds: list[discord.Embed]):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= len(embeds) - 1
        self.page_button.label = f"Page {self.current_page + 1}/{len(embeds)}"
        await interaction.response.edit_message(embed=embeds[self.current_page], view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
