import os
import requests
import discord
import asyncio
import aiohttp
import db
from discord.ext import tasks
from pathlib import Path
from datetime import datetime, timezone

# Configuration des clients et constantes
HTB_API_TOKEN = os.environ.get('HTB_API_TOKEN')
HTB_UNIVERSITY_ID = os.environ.get('HTB_UNIVERSITY_ID')  # ID de l'université
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
DISCORD_CHANNEL_ID = int(os.environ.get('DISCORD_CHANNEL_ID', 0))
DISCORD_TODO_CHANNEL_ID = int(os.environ.get('DISCORD_TODO_CHANNEL_ID', 0))

# Configuration des chemins
DATA_DIR = Path("data")

# Id des messages
monitor_messages = {
    "challenges": None,
    "machines": None,
    "fortresses": None
}

# Configuration du client Discord
client = discord.Client(intents=discord.Intents.default())

# Headers de base pour les requêtes API
base_headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
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

async def fetch_member_profile(member_id):
    url = f"https://labs.hackthebox.com/api/v4/user/profile/basic/{member_id}"
    headers = {**base_headers, "Host": "labs.hackthebox.com"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json().get('info', {})
            name = data.get('name', 'Inconnu')
            rank_text = data.get('rank', 'No Rank')
            avatar = data.get('avatar_thumb', '')
            if avatar and not avatar.startswith('http'):
                avatar = f"https://www.hackthebox.com/{avatar.lstrip('/')}"
            return name, rank_text, avatar
        else:
            print(f"[-] Erreur récupération profile {member_id}: {response.status_code} {response.text}")
    except Exception as e:
        print(f"[-] Erreur récupération profile {member_id}: {e}")
    return 'Inconnu', 'No Rank', 'https://avatars.githubusercontent.com/u/128290827?s=200&v=4'

async def get_all_activities(member_id):
    activity_url = f"https://labs.hackthebox.com/api/v4/user/profile/activity/{member_id}"
    headers = {**base_headers, "Host": "labs.hackthebox.com"}
    try:
        response = requests.get(activity_url, headers=headers, timeout=10)
        if response.status_code == 200:
            activities = response.json().get('profile', {}).get('activity', [])
            for activity in activities:
                object_type = activity.get('object_type')
                if object_type == 'machine':
                    flag_type = activity.get('type', None)
                    if flag_type in ('user', 'root'):
                        db.add_machine_flag(str(member_id), str(activity.get('id')), flag_type)
                elif object_type == 'fortress':
                    flag_type = activity.get('flag_title', None)
                    if flag_type:
                        db.add_fortress_flag(str(member_id), str(activity.get('id')), flag_type)
                elif object_type == 'challenge':
                    db.add_challenge_completion(str(member_id), str(activity.get('id')))
            print(f"[+] Activités mises à jour pour membre {member_id}")
            return activities
        else:
            print(f"[-] Erreur lors de la requête d'activité pour l'ID {member_id}: {response.status_code} {response.text}")
    except requests.exceptions.Timeout:
        print(f"[-] Timeout pour la requête d'activité de l'ID {member_id}")
    except Exception as e:
        print(f"[-] Erreur inattendue pour l'ID {member_id}: {str(e)}")
    return []

async def fetch_challenge_category(challenge_id):
    url = f"https://labs.hackthebox.com/api/v4/challenge/info/{challenge_id}"
    headers = {**base_headers, "Host": "labs.hackthebox.com"}
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    challenge_info = data.get('challenge', {})
                    category = challenge_info.get('category_name', 'Autres')
                    return category if category else 'Autres'
                else:
                    print(f"[-] Erreur récupération catégorie challenge {challenge_id}: {resp.status} {await resp.text()}")
                    return 'Autres'
    except Exception as e:
        print(f"[-] Erreur récupération catégorie challenge {challenge_id}: {e}")
        return 'Autres'

async def fetch_htb_content():
    print("[*] Récupération des contenus HTB...")
    all_content = {
        'challenges': [],
        'machines': [],
        'fortresses': []
    }

    async def fetch_with_retry(url, host, max_retries=5, delay=3):
        headers = {**base_headers, "Host": host}
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(url, timeout=10) as resp:
                        if resp.status == 200:
                            try:
                                return await resp.json()
                            except aiohttp.client_exceptions.ContentTypeError as e:
                                print(f"[-] Erreur JSON pour {url}: {e}")
                                return None
                        else:
                            print(f"[-] Statut HTTP {resp.status} pour {url}: {await resp.text()}")
                            return None
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"[-] Tentative {attempt + 1} échouée pour {url}: {e}")
                await asyncio.sleep(delay * (attempt + 1))
        return None

    # Récupération des challenges
    challenge_url = "https://labs.hackthebox.com/api/v4/challenge/list"
    challenges_data = await fetch_with_retry(challenge_url, "labs.hackthebox.com")
    if challenges_data and 'challenges' in challenges_data:
        for c in challenges_data.get('challenges', []):
            if c.get('id') and c.get('name'):
                category = await fetch_challenge_category(c['id'])
                all_content['challenges'].append({
                    'id': str(c['id']),
                    'name': c['name'],
                    'difficulty': f"{c.get('difficulty', 'Inconnue')} ({c.get('avg_difficulty', 0)}/100)",
                    'points': int(str(c.get('points', '0')).strip() or '0'),
                    'challenge_category': category
                })
                await asyncio.sleep(0.5)  # Délai pour éviter de surcharger l'API
        print(f"[+] {len(all_content['challenges'])} challenges récupérés")
    else:
        print(f"[-] Échec de la récupération des challenges depuis {challenge_url}, utilisation des données en base")
        all_content['challenges'] = [
            {'id': row[0], 'name': row[1], 'difficulty': row[2], 'points': row[3], 'challenge_category': row[4]}
            for row in db.get_all_challenges()
        ]
        print(f"[+] {len(all_content['challenges'])} challenges chargés depuis la base")

    # Récupération des machines
    machines_data = await fetch_with_retry("https://labs.hackthebox.com/api/v4/machine/paginated?retired=0", "labs.hackthebox.com")
    if machines_data and 'data' in machines_data:
        for m in machines_data['data']:
            if m.get('id') and m.get('name'):
                all_content['machines'].append({
                    'id': str(m['id']),
                    'name': m['name'],
                    'difficulty': f"{m.get('difficultyText', 'Inconnu')} ({m.get('difficulty', 0)}/100)",
                    'points': int(m.get('points', 0)),
                    'os': m.get('os', 'Inconnu')
                })
        print(f"[+] {len(all_content['machines'])} machines récupérées")
    else:
        print("[-] Échec de la récupération des machines, utilisation des données en base")
        all_content['machines'] = [
            {'id': row[0], 'name': row[1], 'difficulty': row[2], 'points': row[3], 'os': row[4]}
            for row in db.get_all_machines()
        ]
        print(f"[+] {len(all_content['machines'])} machines chargées depuis la base")

    # Récupération des forteresses
    fortresses_data = await fetch_with_retry("https://labs.hackthebox.com/api/v4/fortresses", "labs.hackthebox.com")
    if fortresses_data and fortresses_data.get('data'):
        for f in fortresses_data['data'].values():
            if isinstance(f, dict) and f.get('id') and f.get('name'):
                fortress_id = str(f.get('id', '0'))
                name = f.get('name', 'Inconnu')
                points = f.get('points', None)
                number_of_flags = f.get('number_of_flags', 0)
                if points is None:
                    points = number_of_flags * 10
                all_content['fortresses'].append({
                    'id': fortress_id,
                    'name': name,
                    'points': points,
                    'number_of_flags': number_of_flags
                })
            else:
                print(f"[-] Forteresse ignorée, données invalides: {f}")
        print(f"[+] {len(all_content['fortresses'])} forteresses récupérées")
    else:
        print("[-] Échec de la récupération des forteresses, utilisation des données en base")
        all_content['fortresses'] = [
            {'id': row[0], 'name': row[1], 'points': row[2], 'number_of_flags': row[3]}
            for row in db.get_all_fortresses()
        ]
        print(f"[+] {len(all_content['fortresses'])} forteresses chargées depuis la base")

    return all_content

async def update_discord_todo_list(channel, todo_rows):
    colors = {
        'challenges': 0x00ff00,
        'machines': 0x0000ff,
        'fortresses': 0xff0000
    }
    embeds = {}

    # Challenges
    challenge_rows = [x for x in todo_rows if x[0] == 'challenge']
    if challenge_rows:
        embed = discord.Embed(
            title="Challenges à compléter",
            color=colors['challenges'],
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="HTB Univ tracker")
        all_chall = {row[0]: row for row in db.get_all_challenges()}
        categories = {}
        for _, htb_id, name in challenge_rows:
            chall = all_chall.get(htb_id)
            if chall:
                _, cname, cdiff, cpts, ccat = chall
                ccat = ccat if ccat and ccat != 'Inconnue' else 'Autres'
                categories.setdefault(ccat, []).append((cname, cdiff, cpts))
            else:
                categories.setdefault('Autres', []).append((name, '?', 0))
        
        for cat, items in sorted(categories.items(), key=lambda x: len(x[1]), reverse=True):  # Tri par nombre de challenges
            items_sorted = sorted(items, key=lambda x: x[2], reverse=True)  # Tri par points
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
    else:
        print("[-] Aucun challenge restant à afficher")

    # Machines
    machine_user = [x for x in todo_rows if x[0] == 'machine_user']
    machine_root = [x for x in todo_rows if x[0] == 'machine_root']
    machines = machine_user + machine_root
    if machines:
        embed = discord.Embed(
            title="Machines à compléter",
            color=colors['machines'],
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="HTB Univ tracker")
        all_mach = {row[0]: row for row in db.get_all_machines()}
        machine_flags = {}
        for t, htb_id, name in machines:
            flag = "user" if t == 'machine_user' else 'root'
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
    else:
        print("[-] Aucune machine restante à afficher")

    # Forteresses
    fortress_rows = [x for x in todo_rows if x[0] == 'fortress_flag']
    if fortress_rows:
        embed = discord.Embed(
            title="Forteresses à compléter",
            color=colors['fortresses'],
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="HTB Univ tracker")
        all_fort = {row[0]: row for row in db.get_all_fortresses()}
        fortress_flags_map = {}
        for _, htb_key, name in fortress_rows:
            try:
                fortress_id, flag_type = htb_key.split(':', 1)
                if fortress_id not in fortress_flags_map:
                    fortress_flags_map[fortress_id] = {'name': name, 'missing_flags': []}
                fortress_flags_map[fortress_id]['missing_flags'].append(flag_type)
            except ValueError:
                print(f"[-] Clé de forteresse invalide: {htb_key}")
                continue
        
        async with aiohttp.ClientSession(headers={**base_headers, "Host": "labs.hackthebox.com"}) as session:
            for fortress_id, info in fortress_flags_map.items():
                fort = all_fort.get(fortress_id)
                missing_flags = sorted(info['missing_flags'])
                flag_url = f"https://labs.hackthebox.com/api/v4/fortress/{fortress_id}/flags"
                total_points = 0
                try:
                    async with session.get(flag_url, timeout=10) as resp:
                        if resp.status == 200:
                            flag_data = await resp.json()
                            if flag_data.get('status') and isinstance(flag_data['data'], list):
                                for flag in flag_data['data']:
                                    if flag.get('title') in missing_flags:
                                        total_points += flag.get('points', 0)
                            else:
                                print(f"[-] Données flags invalides pour forteresse {fortress_id}: {flag_data}")
                        else:
                            print(f"[-] Statut HTTP {resp.status} pour {flag_url}: {await resp.text()}")
                except Exception as e:
                    print(f"[-] Erreur récupération flags pour forteresse {fortress_id}: {e}")
                    total_points = fort[2] if fort else 0
                missing_str = ", ".join(missing_flags)
                num_missing = len(missing_flags)
                value = f"Flags restants: {num_missing}\nPoints restants: {total_points}\nFlags à faire: {missing_str}"
                if fort:
                    _, fname, _, total_flags = fort
                    embed.add_field(
                        name=fname,
                        value=value,
                        inline=False
                    )
                else:
                    embed.add_field(name=info["name"], value=f"{value}\n(infos manquantes)", inline=False)
                await asyncio.sleep(0.5)
        embeds["fortresses"] = embed
    else:
        print("[-] Aucun flag forteresse restant à afficher")

    for category in monitor_messages.keys():
        if monitor_messages[category]:
            try:
                message = await channel.fetch_message(monitor_messages[category])
                if embeds.get(category):
                    await message.edit(embed=embeds[category])
                else:
                    await message.delete()
                    monitor_messages[category] = None
            except discord.errors.NotFound:
                if embeds.get(category):
                    message = await channel.send(embed=embeds[category])
                    monitor_messages[category] = message.id
        elif embeds.get(category):
            message = await channel.send(embed=embeds[category])
            monitor_messages[category] = message.id

    return challenge_rows, machine_user, machine_root, fortress_rows

@tasks.loop(minutes=5)
async def check_member_progress():
    print("[*] Vérification des progrès des membres...")
    members = []
    if not HTB_UNIVERSITY_ID:
        print("[-] HTB_UNIVERSITY_ID non défini. Veuillez définir la variable d'environnement HTB_UNIVERSITY_ID avec l'ID de votre université.")
        return
    university_url = f"https://labs.hackthebox.com/api/v4/university/members/{HTB_UNIVERSITY_ID}"
    headers = {**base_headers, "Host": "labs.hackthebox.com"}
    try:
        response = requests.get(university_url, headers=headers, timeout=10)
        if response.status_code == 200:
            members = response.json()
            print(f"[+] {len(members)} membres trouvés")
        else:
            print(f"[-] Erreur récupération membres: {response.status_code} {response.text}")
            return
    except Exception as e:
        print(f"[-] Erreur lors de la récupération des membres: {e}")
        return
    channel = client.get_channel(DISCORD_CHANNEL_ID)
    todo_channel = client.get_channel(DISCORD_TODO_CHANNEL_ID)
    if not channel:
        print(f"[-] Channel Discord ID {DISCORD_CHANNEL_ID} non trouvé")
        return
    if not todo_channel:
        print(f"[-] Channel Discord ID {DISCORD_TODO_CHANNEL_ID} non trouvé")
        return
    for member in members:
        member_id = str(member['id'])
        activities = await get_all_activities(member_id)
        if activities:
            latest_activity = activities[0]
            object_type = latest_activity.get('object_type')
            added = False
            todo_type = None
            todo_id = None
            if object_type == 'challenge':
                chall_id = str(latest_activity.get('id'))
                if chall_id not in db.get_challenge_completions(member_id):
                    db.add_challenge_completion(member_id, chall_id)
                    added = True
                    todo_type = 'challenge'
                    todo_id = chall_id
            elif object_type == 'machine':
                flag_type = latest_activity.get('type')
                if flag_type in ('user', 'root'):
                    machine_id = str(latest_activity.get('id'))
                    if flag_type not in db.get_machine_flags(member_id, machine_id):
                        db.add_machine_flag(member_id, machine_id, flag_type)
                        added = True
                        todo_type = f'machine_{flag_type}'
                        todo_id = machine_id
            elif object_type == 'fortress':
                flag_title = latest_activity.get('flag_title')
                if flag_title:
                    fortress_id = str(latest_activity.get('id'))
                    if flag_title not in db.get_fortress_flags(member_id, fortress_id):
                        db.add_fortress_flag(member_id, fortress_id, flag_title)
                        added = True
                        todo_type = 'fortress_flag'
                        todo_id = f"{fortress_id}:{flag_title}"
            if added and todo_type and todo_id:
                conn = db.sqlite3.connect(db.DB_PATH)
                c = conn.cursor()
                c.execute("SELECT * FROM todo WHERE type = ? AND htb_id = ?", (todo_type, todo_id))
                if c.fetchone():
                    _, rank_text, thumbnail = await fetch_member_profile(member_id)
                    name = latest_activity.get('name', 'Inconnu')
                    points = latest_activity.get('points', 0)
                    if str(points) == '0':
                        name = f"{name} Retraité"
                    if object_type == 'machine':
                        category = flag_type.upper()
                        activity_type = 'Machine'
                    elif object_type == 'challenge':
                        category = await fetch_challenge_category(chall_id)
                        activity_type = 'Challenge'
                    elif object_type == 'fortress':
                        category = flag_title
                        activity_type = 'Fortress Flag'
                    embed = discord.Embed(
                        title=f":drop_of_blood: First blood de {name} !",
                        description=(
                            f"**Pseudo** : `{member['name']}`\n"
                            f"**Type** : `{activity_type}`\n"
                            f"**Catégorie** : `{category}`\n"
                            f"**Points** : `+{points}`\n"
                            f"**Rank** : `{rank_text}`"
                        ),
                        color=0xFF0000,
                    )
                    embed.set_footer(text="GCC University First Blood Tracker")
                    embed.set_thumbnail(url=thumbnail)
                    await channel.send(embed=embed)
                    db.remove_todo(todo_type, todo_id)
                    # Mettre à jour la liste todo sur Discord
                    todo_rows = db.get_todo()
                    challenge_rows, machine_user, machine_root, fortress_rows = await update_discord_todo_list(todo_channel, todo_rows)
                    print("[*] Liste todo mise à jour sur Discord après nouveau flag")
                    print("[*] Résumé des défis restants:")
                    print(f"    - Challenges: {len(challenge_rows)}")
                    print(f"    - Machines (user): {len(machine_user)}")
                    print(f"    - Machines (root): {len(machine_root)}")
                    print(f"    - Fortress Flags: {len(fortress_rows)}")
                conn.close()
        await asyncio.sleep(0.3)

@tasks.loop(minutes=1)
async def weekly_update():
    now = datetime.now(timezone.utc)
    # Samedi = jour 5 (0=dimanche, 1=lundi, ..., 5=samedi), 20h10 CEST = 18h10 UTC
    if now.weekday() == 5 and now.hour == 18 and now.minute >= 10 and now.minute < 11:
        print("[*] Exécution de la mise à jour hebdomadaire (samedi 20h10 CEST)...")
        await daily_update()
    await asyncio.sleep(60)  # Attendre 60 secondes avant la prochaine vérification

async def daily_update():
    print("[*] Début de la mise à jour hebdomadaire...")
    try:
        # Récupérer les membres de l'université
        members = []
        if not HTB_UNIVERSITY_ID:
            print("[-] HTB_UNIVERSITY_ID non défini. Veuillez définir la variable d'environnement HTB_UNIVERSITY_ID avec l'ID de votre université.")
            return
        university_url = f"https://labs.hackthebox.com/api/v4/university/members/{HTB_UNIVERSITY_ID}"
        headers = {**base_headers, "Host": "labs.hackthebox.com"}
        try:
            response = requests.get(university_url, headers=headers, timeout=10)
            if response.status_code == 200:
                members = response.json()
                print(f"[+] {len(members)} membres trouvés et enregistrés en base")
                for member in members:
                    db.add_or_update_user(str(member['id']), member['name'])
            else:
                print(f"[-] Erreur récupération membres: {response.status_code} {response.text}")
                return
        except Exception as e:
            print(f"[-] Erreur lors de la récupération des membres: {e}")
            return

        # Récupérer le contenu HTB
        content = await fetch_htb_content()
        
        # Mettre à jour les challenges
        print("[*] Mise à jour des challenges en base...")
        for c in content['challenges']:
            db.add_or_update_challenge(c['id'], c['name'], c['difficulty'], c['points'], c['challenge_category'])
        
        # Mettre à jour les machines
        print("[*] Mise à jour des machines en base...")
        for m in content['machines']:
            db.add_or_update_machine(m['id'], m['name'], m['difficulty'], m['points'], m['os'])
        
        # Mettre à jour les forteresses
        print("[*] Mise à jour des forteresses en base...")
        for f in content['fortresses']:
            db.add_or_update_fortress(f['id'], f['name'], f['points'], f['number_of_flags'])

        # Vérifier toutes les activités des membres pour mettre à jour les complétions
        print("[*] Mise à jour des complétions pour tous les membres...")
        for member in members:
            member_id = str(member['id'])
            await get_all_activities(member_id)
            await asyncio.sleep(0.5)

        # Reconstruire la todo list
        db.clear_todo()

        print("[*] Ajout des challenges à la todo...")
        all_challenges = {row[0]: row for row in db.get_all_challenges()}
        for challenge_id, challenge in all_challenges.items():
            completed = False
            for member in members:
                if challenge_id in db.get_challenge_completions(str(member['id'])):
                    completed = True
                    break
            if not completed:
                db.add_todo('challenge', challenge_id, challenge[1])

        print("[*] Ajout des machines à la todo...")
        all_machines = {row[0]: row for row in db.get_all_machines()}
        for machine_id, machine in all_machines.items():
            user_flags = set()
            root_flags = set()
            for member in members:
                flags = db.get_machine_flags(str(member['id']), machine_id)
                for flag in flags:
                    if flag == 'user':
                        user_flags.add(str(member['id']))
                    elif flag == 'root':
                        root_flags.add(str(member['id']))
            if not user_flags:
                db.add_todo('machine_user', machine_id, machine[1])
            if not root_flags:
                db.add_todo('machine_root', machine_id, machine[1])
        
        print("[*] Ajout des forteresses à la todo...")
        all_fortresses = {row[0]: row for row in db.get_all_fortresses()}
        async with aiohttp.ClientSession(headers={**base_headers, "Host": "labs.hackthebox.com"}) as session:
            for fortress_id, fortress in all_fortresses.items():
                flag_url = f"https://labs.hackthebox.com/api/v4/fortress/{fortress_id}/flags"
                try:
                    async with session.get(flag_url, timeout=10) as resp:
                        if resp.status == 200:
                            flag_data = await resp.json()
                            if flag_data.get('status') and isinstance(flag_data['data'], list):
                                all_flags = [flag['title'] for flag in flag_data['data']]
                                for flag in all_flags:
                                    completed = False
                                    for member in members:
                                        if flag in db.get_fortress_flags(str(member['id']), fortress_id):
                                            completed = True
                                            break
                                    if not completed:
                                        db.add_todo('fortress_flag', f"{fortress_id}:{flag}", fortress[1])
                            else:
                                print(f"[-] Données flags invalides pour forteresse {fortress_id}: {flag_data}")
                        else:
                            print(f"[-] Statut HTTP {resp.status} pour {flag_url}: {await resp.text()}")
                except Exception as e:
                    print(f"[-] Erreur récupération flags pour forteresse {fortress_id}: {e}")
                await asyncio.sleep(0.5)
        
        print("[+] Table todo mise à jour en base")

        # Envoi de la liste sur Discord
        print("[*] Envoi de la liste sur Discord...")
        channel = client.get_channel(DISCORD_TODO_CHANNEL_ID)
        if not channel:
            print(f"[-] Channel Discord ID {DISCORD_TODO_CHANNEL_ID} non trouvé")
            return
        todo_rows = db.get_todo()
        challenge_rows, machine_user, machine_root, fortress_rows = await update_discord_todo_list(channel, todo_rows)
        
        print("[*] Résumé des défis restants:")
        print(f"    - Challenges: {len(challenge_rows)}")
        print(f"    - Machines (user): {len(machine_user)}")
        print(f"    - Machines (root): {len(machine_root)}")
        print(f"    - Fortress Flags: {len(fortress_rows)}")
        print("[+] Mise à jour terminée")
    except Exception as e:
        print(f"[-] Erreur dans daily_update: {e}")

@client.event
async def on_ready():
    print(f"[+] Connecté en tant que {client.user.name}")
    print("[*] Initialisation...")
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True)
    db.init_db()
    # Exécuter la mise à jour initiale au démarrage
    print("[*] Exécution de la mise à jour initiale au démarrage...")
    await daily_update()
    check_member_progress.start()
    weekly_update.start()
    print("[+] Bot prêt !")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("[!] Token Discord non configuré, mode bot désactivé")
        exit(1)
    if not HTB_API_TOKEN:
        print("[!] Token API HTB non configuré")
        exit(1)
    if not HTB_UNIVERSITY_ID:
        print("[!] HTB_UNIVERSITY_ID non défini. Veuillez définir la variable d'environnement HTB_UNIVERSITY_ID avec l'ID de votre université.")
        exit(1)
    print("[*] Démarrage du bot Discord...")
    client.run(DISCORD_TOKEN)
