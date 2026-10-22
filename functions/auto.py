"""
title: Auto
author: Company AI kit
description: Reads each message and hands it to the best assistant or model.
version: 1.0.0
"""

# Installed into Open WebUI by setup.py as a "pipe" function. It appears in the
# model menu as "Auto". For every message it asks a fast model which kind of
# work this is, then forwards the whole conversation to the matching assistant
# (which brings its own instructions, temperature and document search) or to a
# specialist model for reasoning or code.

import logging
import re

from pydantic import BaseModel, Field

from open_webui.models.models import Models
from open_webui.models.skills import Skills, get_skill_snapshot
from open_webui.models.users import Users
from open_webui.utils.chat import generate_chat_completion

log = logging.getLogger(__name__)

CATEGORIES = {
    "documents": "questions about company policies, projects, prices, procedures, HR rules, or anything that would be in company files",
    "sales": "handling a customer: objections, follow-up messages, pitches, comparing options for a buyer",
    "writing": "drafting, rewriting or translating emails, listings, posts, letters, reports or minutes",
    "reasoning": "maths, logic, puzzles, multi-step planning, or careful analysis of a tricky question",
    "code": "programming, spreadsheet formulas, SQL, data files or converting data",
    "general": "everything else: explanations, quick questions, brainstorming, small talk",
}


class Pipe:
    class Valves(BaseModel):
        CLASSIFIER_MODEL: str = Field(default="", description="Fast model that decides the category. Empty: same as GENERAL_TARGET.")
        DOCUMENTS_TARGET: str = Field(default="company-knowledge")
        SALES_TARGET: str = Field(default="sales-assistant")
        WRITING_TARGET: str = Field(default="writing-assistant")
        GENERAL_TARGET: str = Field(default="general-assistant")
        REASONING_TARGET: str = Field(default="", description="e.g. deepseek-r1:8b. Empty: use GENERAL_TARGET.")
        CODE_TARGET: str = Field(default="", description="e.g. qwen3.5:9b. Empty: use GENERAL_TARGET.")
        SHOW_CHOICE: bool = Field(default=True, description="Show which assistant answered, above the reply.")

    def __init__(self):
        self.valves = self.Valves()

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _text(message):
        content = message.get("content", "")
        if isinstance(content, list):
            content = " ".join(part.get("text", "") for part in content if isinstance(part, dict))
        return content or ""

    def _question(self, messages):
        """The user's latest message, without the document excerpts the app may have wrapped around it."""
        for message in reversed(messages):
            if message.get("role") == "user":
                text = self._text(message)
                if "</context>" in text:
                    text = text.rsplit("</context>", 1)[1]
                return text.strip()
        return ""

    def _targets(self):
        v = self.valves
        return {
            "documents": v.DOCUMENTS_TARGET,
            "sales": v.SALES_TARGET,
            "writing": v.WRITING_TARGET,
            "reasoning": v.REASONING_TARGET or v.GENERAL_TARGET,
            "code": v.CODE_TARGET or v.GENERAL_TARGET,
            "general": v.GENERAL_TARGET,
        }

    @staticmethod
    async def _skills_for(target):
        """The skills pinned to the target assistant, as system text. The hand-off below
        skips the app layer that normally adds them, so the router adds them itself."""
        model_info = await Models.get_model_by_id(target)
        skill_ids = (model_info.meta.model_dump().get("skillIds") if model_info and model_info.meta else None) or []
        blocks = []
        for skill_id in skill_ids:
            try:
                skill = await Skills.get_skill_by_id(skill_id)
                if not skill:
                    continue
                content = (await get_skill_snapshot(skill)).get("content", "")
                blocks.append(f'<skill id="{skill.id}" name="{skill.name}">\n{content}\n</skill>')
            except Exception as e:
                log.warning("Auto router: could not load skill %s (%s)", skill_id, e)
        return "\n\n".join(blocks)

    async def _classify(self, request, user, question, history):
        lines = "\n".join(f"- {name}: {what}" for name, what in CATEGORIES.items())
        prompt = (
            "You route messages inside a company assistant. Pick the single best category for the "
            f"user's latest message.\n\nCategories:\n{lines}\n\n"
            f"Recent conversation:\n{history}\n\nLatest message:\n{question}\n\n"
            "Reply with exactly one word: the category name."
        )
        model = self.valves.CLASSIFIER_MODEL or self.valves.GENERAL_TARGET
        try:
            res = await generate_chat_completion(
                request,
                {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "temperature": 0,
                    "max_tokens": 10,
                    "think": False,
                },
                user,
                bypass_filter=True,
            )
            content = (res.get("choices") or [{}])[0].get("message", {}).get("content") or res.get("message", {}).get("content", "")
            words = re.findall(r"[a-z]+", content.lower())
            for word in words:
                if word in CATEGORIES:
                    return word
        except Exception as e:
            log.warning("Auto router: classification failed, using general (%s)", e)
        return "general"

    # --------------------------------------------------------------- main

    async def pipe(self, body: dict, __user__: dict, __request__, __event_emitter__=None, __metadata__=None):
        user = await Users.get_user_by_id(__user__["id"])
        messages = body.get("messages", [])
        question = self._question(messages)
        history = "\n".join(
            f"{m.get('role')}: {self._text(m)[:200]}" for m in messages[-5:-1] if m.get("role") in ("user", "assistant")
        )

        category = await self._classify(__request__, user, question, history) if question else "general"
        targets = self._targets()
        target = targets.get(category) or targets["general"]
        models = __request__.app.state.MODELS
        if target not in models:
            log.warning("Auto router: target %s not available, using %s", target, targets["general"])
            target, category = targets["general"], "general"
        if target not in models:
            raise Exception(f"Auto router: no model available for '{category}'. Run setup again.")

        name = models[target].get("name", target)
        if __event_emitter__ and self.valves.SHOW_CHOICE:
            await __event_emitter__(
                {"type": "status", "data": {"description": f"Answered by {name}", "done": True}}
            )

        skills_text = await self._skills_for(target)
        if skills_text:
            # Keep whatever system context the app already added (e.g. the user's memories)
            # and append the skills to it. The assistant's own instructions are added on hand-off.
            existing = "\n\n".join(self._text(m) for m in messages if m.get("role") == "system")
            system = f"{existing}\n\n{skills_text}".strip()
            messages = [{"role": "system", "content": system}] + [m for m in messages if m.get("role") != "system"]
        return await generate_chat_completion(__request__, {**body, "model": target, "messages": messages}, user)
