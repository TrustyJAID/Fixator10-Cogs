from pathlib import Path

import aiohttp
from redbot.core import checks
from redbot.core import commands
from redbot.core.config import Config
from redbot.core.utils import chat_formatting as chat
from redbot.core.utils.data_converter import DataConverter as dc

from .godvilleuser import GodvilleUser

BASE_API = "https://godville.net/gods/api/"
BASE_API_GLOBAL = "http://godvillegame.com/gods/api/"


class GodvilleData(commands.Cog):
    """Get data about Godville profiles"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=0x7894D37506AB41B0A1C9F63388EC3A25
        )
        default_user = {
            "godville": {"apikey": None, "godname": None},
            "godvillegame": {"apikey": None, "godname": None},
        }
        self.config.register_user(**default_user)
        self.session = aiohttp.ClientSession(loop=self.bot.loop)

    def __unload(self):
        self.bot.loop.create_task(self.session.close())

    async def api_by_god(self, godname: str, game: str):
        """Get apikey by godname
        :param godname: name of god to get key
        :param game: type of account ("godville" or "godvillegame")"""
        if not any(g == game for g in ["godville", "godvillegame"]):
            raise ValueError(
                f"{game} is not right type of account\n"
                'only "godville" and "godvillegame" are supported'
            )
        users = await self.config.all_users()
        for user, data in users.items():
            if data[game]["godname"] == godname:
                return data[game]["apikey"]
        return None

    @commands.group(invoke_without_command=True)
    @commands.cooldown(30, 10 * 60, commands.BucketType.user)
    async def godville(self, ctx, *, godname: str):
        """Get data about godville's god by name"""
        async with self.session.get(
            "{}/{}/{}".format(
                BASE_API,
                godname.casefold(),
                await self.api_by_god(godname.casefold(), "godville") or "",
            )
        ) as sg:
            if sg.status == 404:
                await ctx.send(
                    chat.error(
                        "404 — Sorry, but there is nothing here\nCheck god name and try again"
                    )
                )
                return
            elif sg.status != 200:
                await ctx.send(
                    chat.error(
                        "Something went wrong. Server returned {}.".format(sg.status)
                    )
                )
                return
            profile = await sg.json()
        profile = GodvilleUser(profile)
        text_header = "{} и его {}\n{}\n".format(
            chat.bold(profile.god),
            chat.bold(profile.name),
            chat.italics(chat.escape(profile.motto.strip(), formatting=True))
            if profile.motto
            else chat.inline("Здесь ничего нет"),
        )
        if profile.arena_is_in_fight:
            text_header += "В сражении: {}\n".format(profile.fight_type_rus)
        if profile.town:
            text_header += "В городе: {}\n".format(profile.town)
        if profile.need_update:
            text_header += chat.bold("! УСТАРЕВШАЯ ИНФОРМАЦИЯ !") + "\n"
        text = ""
        pet = ""
        times = ""
        if profile.gold_approximately:
            text += "Золота: {}\n".format(profile.gold_approximately)
        if profile.distance:
            text += "Столбов от столицы: {}\n".format(profile.distance)
        if profile.quest_progress:
            text += "Задание: {} ({}%)\n".format(profile.quest, profile.quest_progress)
        if profile.experience:
            text += "Опыта до следующего уровня: {}%\n".format(profile.experience)
        text += "Уровень: {}\n".format(profile.level)
        if profile.godpower:
            text += "Праны: {}/{}\n".format(
                profile.godpower, 200 if profile.savings_date else 100
            )
        text += "Характер: {}\n".format(profile.alignment)
        text += "Пол: {}\n".format(profile.gender)
        text += "Побед/Поражений: {}/{}\n".format(profile.arena_won, profile.arena_lost)
        text += (
            "Гильдия: {} ({})\n".format(profile.clan, profile.clan_position)
            if profile.clan
            else "Гильдия: Не состоит\n"
        )
        text += "Кирпичей: {} ({}%)\n".format(profile.bricks, profile.bricks / 10)
        if profile.inventory:
            text += "Инвентарь: {}/{} ({}%)\n".format(
                profile.inventory,
                profile.inventory_max,
                int(profile.inventory / profile.inventory_max * 100),
            )
        else:
            text += "Вместимость инвентаря: {}\n".format(profile.inventory_max)
        if profile.health:
            text += "Здоровье: {}/{} ({}%)\n".format(
                profile.health,
                profile.health_max,
                int(profile.health / profile.health_max * 100),
            )
        else:
            text += "Максимум здоровья: {}\n".format(profile.health_max)
        if profile.ark_male:
            text += "Тварей ♂: {} ({}%)\n".format(
                profile.ark_male, profile.ark_male / 10
            )
        if profile.ark_female:
            text += "Тварей ♀: {} ({}%)\n".format(
                profile.ark_female, profile.ark_female / 10
            )
        if profile.savings:
            text += "Сбережений: {}\n".format(profile.savings)
        if profile.trading_level:
            text += "Уровень торговли: {}\n".format(profile.trading_level)
        if profile.wood:
            text += "Поленьев: {} ({}%)\n".format(profile.wood, profile.wood / 10)

        # private (api only)
        if profile.diary_last:
            text += "Дневник: {}\n".format(profile.diary_last)
        if profile.activatables:
            text += "Активируемое в инвентаре: {}\n".format(
                ", ".join(profile.activatables)
            )
        if profile.aura:
            text += "Аура: {}\n".format(profile.aura)

        # pet
        if profile.pet.name:
            pet += "Имя: {}\n".format(profile.pet.name)
            pet += "Уровень: {}\n".format(profile.pet.level or "Без уровня")
            if profile.pet.type:
                pet += "Тип: {}\n".format(profile.pet.type)
            if profile.pet.wounded:
                pet += "❌ — Контужен"

        # times
        if profile.temple_date:
            times += "Храм достроен: {}\n".format(profile.date_string("temple"))
        if profile.ark_date:
            times += "Ковчег достроен: {}\n".format(profile.date_string("ark"))
        if profile.savings_date:
            times += "Пенсия собрана: {}\n".format(profile.date_string("savings"))

        finaltext = ""
        finaltext += text_header
        finaltext += chat.box(text)
        if pet:
            finaltext += "Питомец:\n"
            finaltext += chat.box(pet)
        if times:
            finaltext += chat.box(times)
        await ctx.send(finaltext)

    @commands.group(invoke_without_command=True)
    @commands.cooldown(30, 10 * 60, commands.BucketType.user)
    async def godvillegame(self, ctx, *, godname: str):
        """Get data about godville's god by name"""
        async with self.session.get(
            "{}/{}".format(BASE_API_GLOBAL, godname.casefold())
        ) as sg:
            if sg.status == 404:
                await ctx.send(
                    chat.error(
                        "404 — Sorry, but there is nothing here\nCheck god name and try again"
                    )
                )
                return
            elif sg.status != 200:
                await ctx.send(
                    chat.error(
                        "Something went wrong. Server returned {}.".format(sg.status)
                    )
                )
                return
            profile = await sg.json()
        profile = GodvilleUser(profile)
        text_header = "{} and his {}\n{}\n".format(
            chat.bold(profile.god),
            chat.bold(profile.name),
            chat.italics(chat.escape(profile.motto.strip(), formatting=True))
            if profile.motto
            else chat.inline("Nothing here"),
        )
        if profile.arena_is_in_fight:
            text_header += "In fight: {}\n".format(profile.fight_type_rus)
        if profile.town:
            text_header += "In city: {}\n".format(profile.town)
        if profile.need_update:
            text_header += chat.bold("! INFO OUTDATED !") + "\n"
        text = ""
        pet = ""
        times = ""
        if profile.gold_approximately:
            text += "Gold: {}\n".format(profile.gold_approximately)
        if profile.distance:
            text += "Milestone: {}\n".format(profile.distance)
        if profile.quest_progress:
            text += "Quest: {} ({}%)\n".format(profile.quest, profile.quest_progress)
        if profile.experience:
            text += "Exp for next level: {}%\n".format(profile.experience)
        text += "Level: {}\n".format(profile.level)
        if profile.godpower:
            text += "Godpower: {}/{}\n".format(
                profile.godpower, 200 if profile.savings_date else 100
            )
        text += "Personality: {}\n".format(profile.alignment)
        text += "Gender: {}\n".format(profile.gender)
        text += "Wins / Losses: {}/{}\n".format(profile.arena_won, profile.arena_lost)
        text += (
            "Guild: {} ({})\n".format(profile.clan, profile.clan_position)
            if profile.clan
            else "Guild: Not in guild\n"
        )
        text += "Bricks: {} ({}%)\n".format(profile.bricks, profile.bricks / 10)
        if profile.inventory:
            text += "Inventory: {}/{} ({}%)\n".format(
                profile.inventory,
                profile.inventory_max,
                int(profile.inventory / profile.inventory_max * 100),
            )
        else:
            text += "Inventory max: {}\n".format(profile.inventory_max)
        if profile.health:
            text += "Health: {}/{} ({}%)\n".format(
                profile.health,
                profile.health_max,
                int(profile.health / profile.health_max * 100),
            )
        else:
            text += "Health maximum: {}\n".format(profile.health_max)
        if profile.ark_male:
            text += "Manimals: {} ({}%)\n".format(
                profile.ark_male, profile.ark_male / 10
            )
        if profile.ark_female:
            text += "Fenimals: {} ({}%)\n".format(
                profile.ark_female, profile.ark_female / 10
            )
        if profile.savings:
            text += "Savings: {}\n".format(profile.savings)
        if profile.trading_level:
            text += "Trading Level: {}\n".format(profile.trading_level)
        if profile.wood:
            text += "Wood: {} ({}%)\n".format(profile.wood, profile.wood / 10)

        # private (api only)
        if profile.diary_last:
            text += "Diary: {}\n".format(profile.diary_last)
        if profile.activatables:
            text += "Activatables in inv: {}\n".format(", ".join(profile.activatables))
        if profile.aura:
            text += "Aura: {}\n".format(profile.aura)

        # pet
        if profile.pet.name:
            pet += "Name: {}\n".format(profile.pet.name)
            pet += "Level: {}\n".format(profile.pet.level or "No level")
            if profile.pet.type:
                pet += "Type: {}\n".format(profile.pet.type)
            if profile.pet.wounded:
                pet += "❌ — Knocked out"

        # times
        if profile.temple_date:
            times += "Temple completed: {}\n".format(profile.date_string("temple"))
        if profile.ark_date:
            times += "Ark completed: {}\n".format(profile.date_string("ark"))
        if profile.savings_date:
            times += "Pension collected: {}\n".format(
                profile.date_string("savings")
            )  # ?

        finaltext = ""
        finaltext += text_header
        finaltext += chat.box(text)
        if pet:
            finaltext += "Pet:\n"
            finaltext += chat.box(pet)
        if times:
            finaltext += chat.box(times)
        await ctx.send(finaltext)

    @godville.group(invoke_without_command=True)
    async def apikey(self, ctx: commands.Context, apikey: str, *, godname: str):
        """Set apikey for your character.

        Only one character per user"""
        await self.config.user(ctx.author).godville.apikey.set(apikey)
        await self.config.user(ctx.author).godville.godname.set(godname.casefold())
        await ctx.tick()

    @apikey.command()
    @checks.is_owner()
    async def convertv2(self, ctx, path):
        """Convert data from V2 cog"""
        base_path = Path(path)
        fp = base_path / "data" / "godville" / "config.json"
        if not fp.is_file():
            ctx.send(chat.error("Config is not found, check your path and try again"))
            return
        converter = dc(self.config)

        def conversion_spec(v2data: dict):
            for member in v2data.keys():
                yield {
                    (Config.USER, member): {
                        ("godville",): {
                            "apikey": v2data[member].get("apikey"),
                            "godname": v2data[member].get("godname"),
                        }
                    }
                }

        await converter.convert(fp, conversion_spec)
        await ctx.tick()

    @apikey.command()
    async def remove(self, ctx: commands.Context):
        """Remove your apikey and godname from bot's data"""
        await self.config.user(ctx.author).clear()
        await ctx.tick()
