# Company AI

A private, ChatGPT-style assistant for your team. It runs on one of your own computers,
costs nothing to run, and never sends your data to an outside AI company.

It comes with an automatic mode and four assistants, ready to use:

| Assistant | What it does |
|---|---|
| **Auto** (default) | Reads each message and hands it to the right assistant or model below. Shows "Answered by …" above the reply. |
| **Company Knowledge** | Answers questions from your company documents, with the source shown. |
| **Writing Assistant** | Drafts emails, listings, social posts, reports and letters in a professional tone. |
| **Sales Assistant** | Project facts, objection handling and follow-up messages for the sales team. |
| **General Assistant** | Everyday help: explanations, summaries, formulas, planning. |

Staff can also pick open models directly from the model menu — Qwen, Llama, Mistral and
DeepSeek by default — for plain chats without company documents. Ten built-in **skills**
(email, property listing, WhatsApp follow-up, objection handling, meeting minutes, social post,
Excel formulas, summarise, translate, report brief) give the assistants a consistent way of
doing common jobs; type `$` in a message to use any of them in any chat.

Built on two free, open-source projects: [Open WebUI](https://github.com/open-webui/open-webui)
(the chat app) and [Ollama](https://ollama.com) (runs the AI models). This repo only adds the
configuration, a theme and a setup script, so there is nothing to program.

---

## 1. What you need

- A computer that stays on while people use the bot (an office PC or server is ideal).
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / Mac) or Docker Engine (Linux). Free.
- Memory and the matching AI model:

| Computer | Set `CHAT_MODEL` to | Speed |
|---|---|---|
| Any PC with 16 GB RAM, no graphics card | `gemma4:e4b` (default) | Slow but fine for a few users. ~1 to 2 sentences per second. |
| PC with an NVIDIA card, 12 GB+ VRAM | `gemma4:12b` | Fast. Good for a whole team. |
| PC with an NVIDIA card, 24 GB+ VRAM | `gemma4:26b` | Fast and noticeably smarter. |
| Mac with Apple Silicon, 24 GB+ | `gemma4:12b` | Fast. See "Mac" under Setup. |

About 10 GB of disk space for the default model, plus 4 to 6 GB for each extra model.

### Models

Two settings in `.env` control the models:

- `CHAT_MODEL` — the one model behind the four assistants. Pick it from the table above.
- `EXTRA_MODELS` — models staff can choose directly from the model menu. The default list
  (`qwen3.5:9b,llama3.1:8b,mistral:7b,deepseek-r1:8b`) is the biggest version of each family
  that fits a 16 GB machine. Set it empty to offer only the four assistants.

Two honest notes about "latest" models:
- The headline versions of Llama 4 and DeepSeek V3/R1 are data-centre models (70 to 670 billion
  parameters, 40 to 400 GB). No office PC can run them. `llama3.1:8b` and `deepseek-r1:8b` are the
  biggest members of those families that fit; `deepseek-r1:8b` is a smaller model trained to
  imitate the big one's step-by-step reasoning.
- Only one model is in memory at a time (`OLLAMA_MAX_LOADED_MODELS=1`). When two people use
  different models, the computer swaps between them, which costs 10 to 60 seconds each time.
  A graphics card with 24 GB or more can hold two at once: set `OLLAMA_MAX_LOADED_MODELS=2`.

To change models later: edit `.env`, then `docker compose up -d` (downloads anything new) and
`docker compose run --rm setup` (updates the menu). Documents, users and chats are untouched.

---

## 2. Setup (about 20 minutes, plus download time)

1. **Install Docker Desktop** and start it. On Windows, accept the WSL 2 prompt if it appears.

2. **Download this repository.** Either `git clone` it, or click *Code > Download ZIP* on GitHub
   and unzip it somewhere permanent, for example `C:\company-ai` or `~/company-ai`.

3. **Create your settings file.** Copy `.env.example` to `.env` (same folder) and open `.env`
   in Notepad or any text editor. Fill in at least:
   - `COMPANY_NAME` — used inside the assistants' instructions
   - `ADMIN_EMAIL` and `ADMIN_PASSWORD` — the first admin login
   - `WEBUI_SECRET_KEY` — any long random text

   Then let the computer choose its own models: on Windows right-click `detect-hardware.ps1`
   and choose *Run with PowerShell*; on Mac/Linux run `sh detect-hardware.sh --apply`.
   It reads the memory and graphics card and writes `COMPOSE_PROFILES`, `CHAT_MODEL` and
   `EXTRA_MODELS` into `.env`. (On Windows, add `-Apply` to write; without it, it only prints.)

4. **Add some documents** (optional now, easy to do later). Put PDFs, Word, Excel or text files
   into the `company-docs` folder. Sub-folders are fine.

5. **Open a terminal in the folder.** Windows: open the folder in Explorer, right-click an empty
   area, choose *Open in Terminal*. Mac: right-click the folder in Finder, *New Terminal at Folder*.

6. **Start it:**

   ```
   docker compose up -d
   ```

   The first start downloads the chat app and the AI models (several GB). Watch the model
   download with `docker compose logs -f model-download` (press Ctrl+C to stop watching).

7. **Configure it** (also safe to run again any time):

   ```
   docker compose run --rm setup
   ```

   This waits for the models, loads `company-docs` and creates the four assistants.
   It prints `=== Done ===` when finished.

8. **Open** [http://localhost:3000](http://localhost:3000) and sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

### Mac (Apple Silicon)

Docker on a Mac cannot use the Mac's graphics chip, so the AI would be slow inside Docker.
Install Ollama directly instead: download it from [ollama.com](https://ollama.com), start it,
then in `.env` set `COMPOSE_PROFILES=` (empty) and `OLLAMA_URL=http://host.docker.internal:11434`.
Everything else is the same.

---

## 3. Let your team in

1. Find the computer's address on your office network (Windows: `ipconfig`, look for *IPv4 Address*;
   Mac: System Settings > Network). Example: `192.168.1.25`.
2. Staff open `http://192.168.1.25:3000` in their browser and click **Sign up**.
3. New accounts are *pending* until you approve them: in the app go to
   **Admin Panel > Users**, click the account and set its role to **user**.

Staff see only the four assistants and their own chats. Admins can review all chats
from the Admin Panel if needed.

Tip: staff can install it like an app on their phone or desktop. In the browser choose
*Add to Home Screen* (phone) or *Install* (Chrome / Edge).

---

## 4. Day to day

| Task | How |
|---|---|
| Add or update documents | Put files in `company-docs`, then `docker compose run --rm setup`. Only new or changed files are processed. |
| Remove a document | Delete it from `company-docs`, then run setup again. |
| Change what an assistant does | Edit the file in `assistants/`, then run setup again (see below). |
| Add an assistant | Copy one of the files in `assistants/`, change `id`, `name` and the instructions, run setup. |
| Add or remove a model from the menu | Edit `EXTRA_MODELS` in `.env`, then `docker compose up -d` and run setup. To take a removed model off the disk: `docker compose exec ollama ollama rm <model>`. |
| Change colours or fonts | Edit `theme/custom.css`, then `docker compose restart open-webui` and hard-refresh the browser (Ctrl+Shift+R). |
| Add or change a skill | Edit or copy a folder in `skills/`, run setup. |
| Change what Auto routes where | Admin Panel > Functions > Auto > Valves (or edit `functions/auto.py` and run setup). |
| Stop | `docker compose down` (data is kept). |
| Start again | `docker compose up -d` |
| See logs | `docker compose logs -f open-webui` |
| Update to a newer version | Pull or download the latest version of this repo, then `docker compose up -d` and run setup again. |
| Back up | All data lives in two Docker volumes. Stop the stack, then `docker run --rm -v company-ai_open-webui-data:/data -v "$PWD":/backup alpine tar czf /backup/company-ai-backup.tgz /data` |

### How "Auto" decides

Auto is a small program (`functions/auto.py`) installed into the chat app. For each message it
asks the chat model one short question — "is this about documents, sales, writing, reasoning,
code or general?" — then hands the whole conversation to the matching assistant, which brings its
own instructions, temperature, document search and skills. Reasoning goes to the DeepSeek model
and code or spreadsheet work to Qwen when those are in `EXTRA_MODELS`; otherwise to General.
Cost: one extra short model call per message. If the choice is ever wrong, staff can pick an
assistant directly from the menu. Admins can change the targets under
**Admin Panel > Functions > Auto > Valves**.

### Skills

Each folder in `skills/` holds one `SKILL.md`: a name, a one-line description and the method the
assistant should follow. Setup loads them all and pins some to each assistant (the `skills:` line
in the assistant file), so they apply automatically; any skill can also be called in any chat by
typing `$` and picking it. To add one, copy a folder, edit the text, run setup. Keep them short
(under 1,500 characters): pinned skills are sent with every message.

These skills are written for this kit. The Claude skills installed in Claude Code (Word, Excel,
PowerPoint, PDF creation and others) are licensed for use inside Anthropic's services only and
cannot be copied into another product, which is why they are not included.

### Does it learn?

Not in the way a person does: the model's knowledge is fixed when it is trained. Three things do
make the bot better over time:

- **Documents** — anything added to `company-docs` is searchable after the next setup run.
  This is the real "learning" for a company bot.
- **Memory** — the bot notes useful facts about each user from their chats (team, projects,
  preferences) and uses them later. Each user can view, edit or switch this off under
  *Settings > Personalization > Memory*.
- **Feedback** — the thumbs up/down under every answer is stored (*Admin Panel > Evaluations*).
  After a few months this gives real examples of good and bad answers; they can be used to
  fine-tune a model on your company's style, which is a separate project needing a strong GPU.

### Assistant files

Each file in `assistants/` has a short header, then the instructions the assistant follows:

```
---
id: sales-assistant          # short, no spaces, never changes
name: Sales Assistant        # shown to staff
description: One line shown under the name.
uses_documents: yes          # yes = can search company-docs
temperature: 0.4             # 0.1 = precise and repetitive, 0.8 = creative
skills: objection-handling, whatsapp-followup   # folders in skills/, always on for this assistant
suggestion: A customer says the price is too high. How should I respond?
suggestion: (as many as you like; shown as buttons on a new chat)
---
You are the sales support assistant for {COMPANY_NAME}. ...
```

`{COMPANY_NAME}` is replaced with the value from `.env`. Files are processed in name order,
which is also the order in the model picker.

---

## 5. Troubleshooting

**"Could not sign in" when running setup.** The password in `.env` must match the admin's
current password. If you changed it in the app, update `.env`.

**A document "could not be read".** Usually a scanned PDF (pictures of pages, no text).
Open it in a PDF tool that offers OCR, save, and run setup again. Empty files are skipped too.

**Answers are slow.** Normal on CPU-only machines. Options: a smaller model (`gemma4:e2b`),
a machine with an NVIDIA card (`COMPOSE_PROFILES=nvidia`), or keep `CONTEXT_LENGTH` at 8192.

**Answers ignore the documents.** Check the document is in **Workspace > Knowledge > Company Documents**,
and ask a more specific question. The bot looks up the 5 most relevant passages per question;
very long questions or chit-chat retrieve poorly.

**Port 3000 is already in use.** Change `PORT` in `.env`, then `docker compose up -d`.

**NVIDIA profile fails to start.** Install the
[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
(Linux) or make sure Docker Desktop's WSL 2 backend sees the GPU (Windows: `nvidia-smi` must work inside WSL).

**Start over completely.** `docker compose down -v` deletes all data, users and chats, then `docker compose up -d` and run setup.

---

## 6. Privacy, limits and licence

- Everything runs on your machine. Nothing goes to OpenAI, Google, Anthropic or anyone else.
  Internet is used only to download the software and models.
- The AI model is good, not perfect. It can be wrong, especially on numbers and dates.
  The assistants are instructed to say when something is not in the documents, but always
  check important facts against the source document (shown under each answer).
- The look is set by `theme/custom.css`: a warm cream palette with a terracotta accent, in
  light and dark mode. It changes colours and fonts only. The chat app still shows
  `BOT_NAME (Open WebUI)` in the title: Open WebUI's licence allows removing its branding only
  for deployments of 50 users or fewer, or with their enterprise licence, so this kit leaves it
  in place. See `https://docs.openwebui.com/license`.
- Versions pinned in `docker-compose.yml`: Open WebUI v0.12.3, Ollama 0.40.8.

---

## How it works

```
 staff browser  ──►  Open WebUI (port 3000)  ──►  Ollama (AI model)
                        │
                        ├── users, chats, settings      (Docker volume: open-webui-data)
                        ├── "Company Documents" library ◄── setup syncs company-docs/
                        └── four assistants             ◄── setup creates from assistants/*.md
```

When someone asks a question, Open WebUI finds the 5 most relevant passages in the document
library (using the `embeddinggemma` model), gives them to the chat model together with the
assistant's instructions, and streams back the answer with sources.
