import os
import requests
import discord
import asyncio
import aiohttp
import db
from discord.ext import tasks
from pathlib import Path
from datetime import time, timezone, datetime

time_21   = time(hour=21, tzinfo=timezone.utc)
time_21_1 = time(hour=21, minute=1, tzinfo=timezone.utc)

time_21 = datetime.time(hour=21, tzinfo=datetime.timezone.utc)
time_21_1 = datetime.time(hour=21, minute=1, tzinfo=datetime.timezone.utc)

# Configuration des clients et constantes
HTB_API_TOKEN = os.environ.get('HTB_API_TOKEN')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
DISCORD_CHANNEL_ID = int(os.environ.get('DISCORD_CHANNEL_ID'))
DISCORD_TODO_CHANNEL_ID = int(os.environ.get('DISCORD_TODO_CHANNEL_ID'))

# Configuration des chemins
DATA_DIR = Path("data")

# Id des messages
monitor_messages = {
    "challenges": None,
    "machines": None,
    "forteresses": None
}

# Configuration du client Discord
client = discord.Client(intents=discord.Intents.default())

headers = {
    "Host": "labs.hackthebox.com",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Authorization": f"Bearer {HTB_API_TOKEN}",
    "Origin": "https://app.hackthebox.com",
    "Connection": "keep-alive",
    "Referer": "https://app.hackthebox.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site"
}

async def get_latest_activity(member_id):
    activity_url = f"https://labs.hackthebox.com/api/v4/user/profile/activity/{member_id}"
    try:
        response = requests.get(activity_url, headers=headers, timeout=10)
        if response.status_code == 200:
            activities = response.json().get('profile', {}).get('activity', [])
            if activities:
                # For machines, check if activity contains flag_type
                activity = activities[0]
                if activity.get('object_type') == 'machine':
                    flag_type = activity.get('type', None)
                    if flag_type in ('user', 'root'):
                        db.add_machine_flag(str(member_id), str(activity.get('id')), flag_type)
                return activity
        else:
            print(f"[-] Erreur lors de la requête d'activité pour l'ID {member_id}: {response.status_code}")
    except requests.exceptions.Timeout:
        print(f"[-] Timeout pour la requête d'activité de l'ID {member_id}")
    except Exception as e:
        print(f"[-] Erreur inattendue pour l'ID {member_id}: {str(e)}")
    return None

async def fetch_htb_content():
    print("[*] Récupération des contenus HTB...")
    challenges = []
    machines = []
    fortresses = []

    async def fetch_with_retry(url, max_retries=3, delay=2):
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=10) as resp:
                        if resp.status == 200:
                            return await resp.json()
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"[!] Tentative {attempt + 1} échouée pour {url}: {e}")
                await asyncio.sleep(delay * (attempt + 1))
        return None

    # Récupération des challenges
    challenges_data = await fetch_with_retry("https://www.hackthebox.com/api/v4/challenge/list")
    if challenges_data:
        challenges = challenges_data
        print(f"[+] {len(challenges)} challenges récupérés")

    # Récupération des machines
    machines_data = await fetch_with_retry("https://www.hackthebox.com/api/v4/machine/paginated?retired=0")
    if machines_data and 'data' in machines_data:
        machines = machines_data['data']
        print(f"[+] {len(machines)} machines récupérées")

    # Récupération des forteresses
    fortresses_data = await fetch_with_retry("https://www.hackthebox.com/api/v4/fortresses")
    if fortresses_data:
        fortresses = fortresses_data
        print(f"[+] {len(fortresses)} forteresses récupérées")

@client.event
async def on_ready():
    print(f"[+] Connecté en tant que {client.user.name}")
    
    # Création du dossier data si nécessaire
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True)
    
    # Démarrage des tâches périodiques
    check_member_progress.start()
    update_htb_content.start()

    tracker = HTBUniversityTracker()
    await tracker.update_university_progress()

    print("[+] Bot prêt !")
    
    if not daily_update.is_running():
        daily_update.start()

@tasks.loop(minutes=5)
async def check_member_progress():
    try:
        print("\n[+] Démarrage d'une nouvelle vérification...")
        url = "https://labs.hackthebox.com/api/v4/university/members/518"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"[-] Erreur lors de la requête API: {response.text}")
            return
        data = response.json()
        print(f"[+] Nombre de membres trouvés: {len(data)}")
        channel = client.get_channel(DISCORD_CHANNEL_ID)
        if not channel:
            print("[-] Impossible de trouver le channel Discord")
            return
        print(f"[+] Channel Discord trouvé: {channel.name}")
        # Récupérer la todo list depuis la base
        todo_rows = db.get_todo()
        todo_challenges = set(htb_id for t, htb_id, _ in todo_rows if t == 'challenge')
        # For machines, track user and root flags separately
        todo_machine_user = set(f"{htb_id}:user" for t, htb_id, _ in todo_rows if t == 'machine_user')
        todo_machine_root = set(f"{htb_id}:root" for t, htb_id, _ in todo_rows if t == 'machine_root')
        todo_fortresses = set(htb_id for t, htb_id, _ in todo_rows if t == 'fortress')
        for member in data:
            member_id = member['id']
            # Attente entre chaque requête pour éviter de surcharger l'API
            await asyncio.sleep(0.5)
            current_activity = await get_latest_activity(member_id)
            await asyncio.sleep(0.5)
            if not current_activity:
                print(f"[-] Pas d'activité trouvée pour {member['name']}")
                continue
            name = current_activity.get('name', 'Inconnu')
            points = current_activity.get('points', 0)
            object_type = current_activity.get('object_type', '')
            activity_id = str(current_activity.get('id', '0'))
            flag_type = current_activity.get('type', None)
            thumbnail = member.get('avatar')
            if thumbnail:
                if not thumbnail.startswith('http'):
                    thumbnail = f"https://labs.hackthebox.com/{thumbnail.lstrip('/')}"
            else:
                thumbnail = 'https://avatars.githubusercontent.com/u/128290827?s=200&v=4'
            # Vérifier si l'activité est dans la todo list
            is_todo = False
            # --- Machines: user and root flags are separate ---
            if object_type == 'machine' and flag_type in ('user', 'root'):
                todo_key = f"{activity_id}:{flag_type}"
                if (flag_type == 'user' and todo_key in todo_machine_user) or (flag_type == 'root' and todo_key in todo_machine_root):
                    is_todo = True
            elif object_type == 'challenge' and activity_id in todo_challenges:
                is_todo = True
            elif object_type == 'fortress' and activity_id in todo_fortresses:
                is_todo = True
            if not is_todo:
                print(f"[!] Activité {object_type} {activity_id} de {member['name']} ignorée (pas dans la todo)")
                continue

            # Détermination du type et de la catégorie
            if object_type == 'machine':
                activity_type = 'Machine'
                category = current_activity.get('type', '').upper()
            elif object_type == 'challenge':
                activity_type = 'Challenge'
                category = current_activity.get('challenge_category', 'Unknown')
            else:
                activity_type = object_type
                category = current_activity.get('type', 'Unknown')
            if str(points) == '0':
                name = f"{name} Retiré"
            embed = discord.Embed(
                title=f":drop_of_blood: First blood de {name} !",
                description=(
                    f"**Pseudo** : `{member['name']}`\n"
                    f"**Type** : `{activity_type}`\n"
                    f"**Catégorie** : `{category}`\n"
                    f"**Points** : `+{points}`\n"
                    f"**Rank** : `{member['rank_text']}`"
                ),
                color=0xFF0000,
            )
            embed.set_footer(text="GCC University First Blood Tracker")
            embed.set_thumbnail(url=thumbnail)
            await channel.send(embed=embed)
            # Remove only the completed flag from todo for machines
            if object_type == 'machine' and flag_type in ('user', 'root'):
                db.remove_todo(f"machine_{flag_type}", activity_id)
            elif object_type == 'challenge':
                db.remove_todo(object_type, activity_id)
            elif object_type == 'fortress':
                db.remove_todo(object_type, activity_id)
            tracker = HTBUniversityTracker()
            await tracker.update_university_progress()
        print("=" * 50)
    except Exception as e:
        print(f"[-] Une erreur est survenue: {e}")
        print(f"[-] Détails de l'erreur:", str(e.__class__.__name__))

@tasks.loop(time=time_21)
async def update_htb_content():
    await fetch_htb_content()

class HTBUniversityTracker:
    def __init__(self):
        self.htb_fetcher = None
        self.university_users = []

    async def load_university_users(self):
        print("[*] Récupération des membres de l'université...")
        url = "https://labs.hackthebox.com/api/v4/university/members/518"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.university_users = [{
                'htb_id': str(member['id']),
                'name': member['name']
            } for member in data]
            for member in self.university_users:
                db.add_or_update_user(member['htb_id'], member['name'])
            print(f"[+] {len(self.university_users)} membres trouvés et enregistrés en base")
        except Exception as e:
            print(f"[-] Erreur lors de la récupération des membres: {e}")
            self.university_users = []

    async def get_user_completed_content(self, user_id: str) -> dict:
        await asyncio.sleep(0.4)
        url = f"https://labs.hackthebox.com/api/v4/user/profile/activity/{user_id}"
        completed = {
            'challenges': set(),
            'machines': set(),
            'fortresses': set()
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        activities = data.get('profile', {}).get('activity', [])
                        for act in activities:
                            if act.get('object_type') == 'challenge':
                                completed['challenges'].add(str(act.get('id')))
                            elif act.get('object_type') == 'machine':
                                completed['machines'].add(str(act.get('id')))
                            elif act.get('object_type') == 'fortress':
                                completed['fortresses'].add(str(act.get('id')))
            return completed
        except Exception as e:
            print(f"[-] Erreur lors de la récupération des défis pour l'utilisateur {user_id}: {e}")
            return {'challenges': set(), 'machines': set(), 'fortresses': set()}

    async def update_university_progress(self):
        from list_challenge import HTBDataFetcher
        print("[*] Mise à jour des défis de l'université...")
        self.htb_fetcher = HTBDataFetcher()
        await self.load_university_users()
        all_content = await self.htb_fetcher.get_all_content()
        # --- Récupérer la catégorie exacte de chaque challenge via l'API ---
        async def fetch_challenge_category(session, challenge_id):
            url = f"https://www.hackthebox.com/api/v4/challenge/info/{challenge_id}"
            try:
                await asyncio.sleep(0.5)
                async with session.get(url, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if 'challenge' in data and 'category_name' in data['challenge']:
                            return data['challenge']['category_name']
                        else:
                            print(f"[!] Catégorie absente pour challenge {challenge_id}. Réponse brute: {data}")
                    else:
                        print(f"[!] Statut HTTP {resp.status} pour challenge {challenge_id}")
            except Exception as e:
                print(f"[!] Erreur récupération catégorie pour challenge {challenge_id}: {e}")
            return ''
        # Enregistre tous les challenges, machines, forteresses en base
        async with aiohttp.ClientSession() as session:
            for c in all_content['challenges']:
                # Récupérer la catégorie exacte
                category = await fetch_challenge_category(session, c['id'])
                db.add_or_update_challenge(str(c['id']), c['name'], c['difficulty'], c['points'], category)
                await asyncio.sleep(0.5)  # Petit délai pour éviter le flood
        for m in all_content['machines']:
            db.add_or_update_machine(str(m['id']), m['name'], m['difficulty'], m['points'], m.get('os', ''))
        for f in all_content['fortresses']:
            db.add_or_update_fortress(str(f['id']), f['name'], f.get('points', 0), f.get('flags', 0))
        all_completed = {
            'challenges': set(),
            'machines': set(),
            'fortresses': set()
        }
        all_completed_flags = {}  # {machine_id: set(['user', 'root'])}
        for user in self.university_users:
            print(f"[*] Vérification des défis complétés par {user['name']}...")
            user_completed = await self.get_user_completed_content(user['htb_id'])
            for content_type in ['challenges', 'machines', 'fortresses']:
                all_completed[content_type].update(user_completed[content_type])
            # Pour chaque activité machine, récupérer les flags user/root
            async with aiohttp.ClientSession(headers=headers) as session:
                url = f"https://labs.hackthebox.com/api/v4/user/profile/activity/{user['htb_id']}"
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        activities = data.get('profile', {}).get('activity', [])
                        for act in activities:
                            if act.get('object_type') == 'machine':
                                machine_id = str(act.get('id'))
                                flag_type = act.get('type', None)
                                if flag_type in ('user', 'root'):
                                    all_completed_flags.setdefault(machine_id, set()).add(flag_type)
        db.clear_todo()
        for c in all_content['challenges']:
            if str(c['id']) not in all_completed['challenges']:
                db.add_todo('challenge', str(c['id']), c['name'])
        for m in all_content['machines']:
            machine_id = str(m['id'])
            completed_flags = all_completed_flags.get(machine_id, set())
            if 'user' not in completed_flags:
                db.add_todo('machine_user', machine_id, m['name'])
            if 'root' not in completed_flags:
                db.add_todo('machine_root', machine_id, m['name'])
        for f in all_content['fortresses']:
            if str(f['id']) not in all_completed['fortresses']:
                db.add_todo('fortress', str(f['id']), f['name'])
        print("[+] Table todo mise à jour en base")
        todo_rows = db.get_todo()
        n_chal = len([x for x in todo_rows if x[0] == 'challenge'])
        n_mach = len([x for x in todo_rows if x[0] == 'machine'])
        n_fort = len([x for x in todo_rows if x[0] == 'fortress'])
        print(f"[*] Résumé des défis restants:")
        print(f"    - Challenges: {n_chal}")
        print(f"    - Machines: {n_mach}")
        print(f"    - Forteresses: {n_fort}")
        if DISCORD_TOKEN and client.is_ready():
            print("[*] Envoi de la liste sur Discord...")
            await self.send_todo_to_discord()

    async def send_todo_to_discord(self):
        try:
            channel = client.get_channel(DISCORD_TODO_CHANNEL_ID)
            if not channel:
                print("[-] Impossible de trouver le channel TODO Discord")
                return

            todo_rows = db.get_todo()
            if not todo_rows:
                await channel.send("Aucun défi à faire ! Félicitations à tous !")
                return

            colors = {
                'challenges': 0x00FF00,  # Vert
                'machines': 0x0000FF,    # Bleu
                'fortresses': 0xFF0000   # Rouge
            }

            # Stockage embeds
            embeds = {
                "challenges": None,
                "machines": None,
                "forteresses": None
            }

            # --- CHALLENGES ---
            challenges = [x for x in todo_rows if x[0] == 'challenge']
            if challenges:
                all_chal = {row[0]: row for row in db.get_all_challenges()}
                cat_map = {}
                for _, htb_id, name in challenges:
                    chal = all_chal.get(htb_id, (htb_id, name, '?', 0, 'Inconnue'))
                    _, cname, cdiff, cpts, ccat = chal
                    ccat = ccat or 'Inconnue'
                    cat_map.setdefault(ccat, []).append((cname, cdiff, cpts))

                embed = discord.Embed(
                    title="Challenges",
                    color=colors['challenges'],
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_footer(text="HTB Univ tracker")

                for cat, items in sorted(cat_map.items(), key=lambda x: len(x[1]), reverse=True):
                    items_sorted = sorted(items, key=lambda x: int(x[2]) if str(x[2]).isdigit() else 0, reverse=True)
                    lines = [f"{name} [{diff.split('(')[0].strip()}] - {pts//10}" for name, diff, pts in items_sorted]
                    field_chunks = []
                    current = ""
                    for line in lines:
                        if len(current) + len(line) + 1 > 1024:
                            field_chunks.append(current)
                            current = line
                        else:
                            current = (current + "\n" if current else "") + line
                    if current:
                        field_chunks.append(current)
                    for i, chunk in enumerate(field_chunks):
                        field_name = f"{cat}" if i == 0 else f"{cat} (suite {i})"
                        embed.add_field(name=field_name, value=chunk, inline=False)

                embeds["challenges"] = embed

            # --- MACHINES ---
            # Collect both user and root flags
            machine_user = [x for x in todo_rows if x[0] == 'machine_user']
            machine_root = [x for x in todo_rows if x[0] == 'machine_root']
            machines = machine_user + machine_root
            if machines:
                embed = discord.Embed(
                    title="Machines",
                    color=colors['machines'],
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_footer(text="HTB Univ tracker")

                all_mach = {row[0]: row for row in db.get_all_machines()}
                # Group by machine and show which flags are missing
                machine_flags = {}
                for t, htb_id, name in machines:
                    flag = "user" if t == "machine_user" else "root"
                    if htb_id not in machine_flags:
                        machine_flags[htb_id] = {"name": name, "missing": []}
                    machine_flags[htb_id]["missing"].append(flag)
                for htb_id, info in machine_flags.items():
                    mach = all_mach.get(htb_id)
                    flags_str = ", ".join(info["missing"])
                    if mach:
                        _, mname, mdiff, mpts, mos = mach
                        embed.add_field(
                            name=mname,
                            value=f"Difficulté: {mdiff}\nOS: {mos}\nPoints: {mpts}\nFlags à faire: {flags_str}",
                            inline=False
                        )
                    else:
                        embed.add_field(name=info["name"], value=f"Flags à faire: {flags_str}\n(infos manquantes)", inline=False)

                embeds["machines"] = embed

            # --- FORTRESSES ---
            fortresses = [x for x in todo_rows if x[0] == 'fortress']
            if fortresses:
                embed = discord.Embed(
                    title="Forteresses",
                    color=colors['fortresses'],
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_footer(text="HTB Univ tracker")

                all_fort = {row[0]: row for row in db.get_all_fortresses()}
                for _, htb_id, name in fortresses:
                    fort = all_fort.get(htb_id)
                    if fort:
                        _, fname, fpts, fflags = fort
                        embed.add_field(
                            name=fname,
                            value=f"Points: {fpts}\nFlags: {fflags}",
                            inline=False
                        )
                    else:
                        embed.add_field(name=name, value="(infos manquantes)", inline=False)

                embeds["forteresses"] = embed
            
            # Edit ou créer les messages dans le channel
            for category in monitor_messages.keys():
                if monitor_messages[category]:
                    try:
                        message = await channel.fetch_message(monitor_messages[category])
                        await message.edit(embed=embeds[category])
                    except discord.errors.NotFound:
                        # Si le message n'existe plus, crée-en un nouveau
                        message = await channel.send(embed=embeds[category])
                        monitor_messages[category] = message.id
                else:
                    # Crée un nouveau message
                    message = await channel.send(embed=embeds[category])
                    monitor_messages[category] = message.id

        except Exception as e:
            print(f"[-] Erreur lors de l'envoi Discord TODO: {e}")

@tasks.loop(time=time_21_1)
async def daily_update():
    """Tâche quotidienne de mise à jour des défis"""
    print("\n[*] Début de la mise à jour quotidienne...")
    tracker = HTBUniversityTracker()
    await tracker.update_university_progress()
    print("[+] Mise à jour terminée")

if __name__ == "__main__":
    # Initialiser la base de données SQLite
    db.init_db()
    
    if DISCORD_TOKEN:
        print("[*] Démarrage du bot Discord...")
        client.run(DISCORD_TOKEN)
    else:
        print("[!] Token Discord non configuré, mode bot désactivé")
