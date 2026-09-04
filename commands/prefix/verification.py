"""
Prefix commands for the server verification system.
Supports: button, reaction, captcha
"""

from __future__ import annotations

import json
import random
import string
from pathlib import Path

import discord
from discord.ext import commands
from discord.ui import View, Button

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CONFIG_FILE = DATA_DIR / "verification.json"

# Pending captcha answers: user_id -> expected answer
_pending_captcha: dict[int, str] = {}


def load_config() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_guild_config(guild_id: int | str) -> dict | None:
    config = load_config()
    return config.get(str(guild_id))


async def assign_verified_role(member: discord.Member, guild: discord.Guild) -> tuple[bool, str]:
    """Try to give the verified role. Returns (success, message)."""
    cfg = get_guild_config(guild.id)
    if not cfg or not cfg.get("verified_role_id"):
        return False, "Verification is not configured for this server."

    role = guild.get_role(int(cfg["verified_role_id"]))
    if role is None:
        return False, "The configured verified role no longer exists."

    if role in member.roles:
        return False, "You are already verified."

    try:
        await member.add_roles(role, reason="User completed verification")
    except discord.Forbidden:
        return False, "I do not have permission to assign the verified role."
    except Exception as e:
        return False, f"An error occurred: `{e}`"

    # Optional log
    log_id = cfg.get("log_channel_id")
    if log_id:
        channel = guild.get_channel(int(log_id))
        if channel and isinstance(channel, discord.TextChannel):
            embed = discord.Embed(
                title="Member Verified",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
            method = cfg.get("method", "button")
            embed.add_field(name="Method", value=method.title(), inline=True)
            embed.set_footer(text="Verification System")
            try:
                await channel.send(embed=embed)
            except Exception:
                pass

    return True, f"You have been verified and given the **{role.name}** role."


# -------------------- Button verification --------------------

class VerifyButton(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verify",
        style=discord.ButtonStyle.green,
        custom_id="persistent_verify_button",
    )
    async def verify_button(self, interaction: discord.Interaction, button: Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Unable to verify you here.", ephemeral=True)
            return

        ok, msg = await assign_verified_role(interaction.user, interaction.guild)
        await interaction.response.send_message(msg, ephemeral=True)


# -------------------- Captcha verification --------------------

class CaptchaView(View):
    def __init__(self, correct: str, options: list[str], user_id: int):
        super().__init__(timeout=60)
        self.correct = correct
        self.user_id = user_id

        for opt in options:
            btn = Button(label=opt, style=discord.ButtonStyle.secondary)

            async def make_callback(interaction: discord.Interaction, choice=opt):
                if interaction.user.id != self.user_id:
                    await interaction.response.send_message(
                        "This captcha is not for you.", ephemeral=True
                    )
                    return

                if choice == self.correct:
                    if not interaction.guild or not isinstance(interaction.user, discord.Member):
                        await interaction.response.send_message("Unable to verify.", ephemeral=True)
                        return
                    ok, msg = await assign_verified_role(interaction.user, interaction.guild)
                    await interaction.response.edit_message(
                        content=msg if ok else msg,
                        embed=None,
                        view=None,
                    )
                else:
                    await interaction.response.edit_message(
                        content="Incorrect. Please try again with a new captcha.",
                        embed=None,
                        view=None,
                    )
                _pending_captcha.pop(self.user_id, None)

            btn.callback = make_callback
            self.add_item(btn)


def generate_captcha() -> tuple[str, list[str], str]:
    """Returns (question, options, correct_answer)."""
    a = random.randint(2, 12)
    b = random.randint(2, 12)
    correct = str(a + b)
    options = {correct}
    while len(options) < 4:
        wrong = str(a + b + random.randint(-5, 5))
        if wrong != correct and int(wrong) > 0:
            options.add(wrong)
    option_list = list(options)
    random.shuffle(option_list)
    question = f"What is **{a} + {b}**?"
    return question, option_list, correct


class CaptchaStartView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Start Captcha",
        style=discord.ButtonStyle.blurple,
        custom_id="persistent_captcha_start",
    )
    async def start_captcha(self, interaction: discord.Interaction, button: Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Unable to verify you here.", ephemeral=True)
            return

        cfg = get_guild_config(interaction.guild.id)
        if not cfg:
            await interaction.response.send_message(
                "Verification is not configured.", ephemeral=True
            )
            return

        role_id = cfg.get("verified_role_id")
        if role_id:
            role = interaction.guild.get_role(int(role_id))
            if role and role in interaction.user.roles:
                await interaction.response.send_message("You are already verified.", ephemeral=True)
                return

        question, options, correct = generate_captcha()
        _pending_captcha[interaction.user.id] = correct

        embed = discord.Embed(
            title="Verification Captcha",
            description=f"{question}\n\nClick the correct answer below.",
            color=discord.Color.blurple(),
        )
        view = CaptchaView(correct, options, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# -------------------- Admin commands --------------------

class VerificationPrefix(commands.Cog):
    """Admin commands to configure the verification system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="setupverify")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def setup_verify(
        self,
        ctx: commands.Context,
        method: str,
        role: discord.Role,
        channel: discord.TextChannel = None,
    ):
        """
        Configure verification.
        Usage: !setupverify <button|reaction|captcha> @VerifiedRole [#log-channel]
        """
        method = method.lower().strip()
        if method not in ("button", "reaction", "captcha"):
            await ctx.send(
                "Invalid method. Choose one of: `button`, `reaction`, `captcha`\n"
                "Example: `!setupverify button @Verified`"
            )
            return

        config = load_config()
        guild_id = str(ctx.guild.id)

        config[guild_id] = {
            "method": method,
            "verified_role_id": role.id,
            "log_channel_id": channel.id if channel else None,
            "reaction_emoji": "✅",  # default for reaction mode
            "panel_message_id": None,
            "panel_channel_id": None,
        }
        save_config(config)

        embed = discord.Embed(
            title="Verification Configured",
            color=discord.Color.green(),
            description=(
                f"**Method:** {method}\n"
                f"**Role:** {role.mention}\n"
                f"**Log channel:** {channel.mention if channel else 'Not set'}"
            ),
        )
        embed.add_field(
            name="Next step",
            value="Run `!sendverify` in the channel where you want the verification panel.",
            inline=False,
        )
        await ctx.send(embed=embed)

    @commands.command(name="sendverify")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def send_verify(self, ctx: commands.Context):
        """Send the verification panel for the configured method."""
        cfg = get_guild_config(ctx.guild.id)
        if not cfg or not cfg.get("verified_role_id"):
            await ctx.send(
                "Verification is not configured yet.\n"
                "Use `!setupverify <button|reaction|captcha> @Role` first."
            )
            return

        method = cfg.get("method", "button")

        if method == "button":
            embed = discord.Embed(
                title="Server Verification",
                description=(
                    "Click the **Verify** button below to gain access to the server.\n\n"
                    "By verifying, you confirm that you have read and agree to the server rules."
                ),
                color=discord.Color.blurple(),
            )
            embed.set_footer(text="Verification System • Button")
            view = VerifyButton()
            msg = await ctx.send(embed=embed, view=view)

        elif method == "reaction":
            emoji = cfg.get("reaction_emoji", "✅")
            embed = discord.Embed(
                title="Server Verification",
                description=(
                    f"React with {emoji} to this message to gain access to the server.\n\n"
                    "By verifying, you confirm that you have read and agree to the server rules."
                ),
                color=discord.Color.blurple(),
            )
            embed.set_footer(text="Verification System • Reaction")
            msg = await ctx.send(embed=embed)
            try:
                await msg.add_reaction(emoji)
            except Exception:
                await ctx.send("Failed to add reaction. Check that the emoji is valid.")
                return

            # Store message id so the reaction listener can find it
            config = load_config()
            config[str(ctx.guild.id)]["panel_message_id"] = msg.id
            config[str(ctx.guild.id)]["panel_channel_id"] = msg.channel.id
            save_config(config)

        elif method == "captcha":
            embed = discord.Embed(
                title="Server Verification",
                description=(
                    "Click **Start Captcha** below and solve a short puzzle to gain access.\n\n"
                    "By verifying, you confirm that you have read and agree to the server rules."
                ),
                color=discord.Color.blurple(),
            )
            embed.set_footer(text="Verification System • Captcha")
            view = CaptchaStartView()
            msg = await ctx.send(embed=embed, view=view)

        else:
            await ctx.send("Unknown verification method in config.")
            return

        try:
            await ctx.message.delete()
        except Exception:
            pass

    @setup_verify.error
    @send_verify.error
    async def verify_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need Administrator permission to use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                "Usage: `!setupverify <button|reaction|captcha> @VerifiedRole [#log-channel]`"
            )
        else:
            await ctx.send(f"An error occurred: `{error}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(VerificationPrefix(bot))
