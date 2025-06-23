import os
import sys
import json
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from rich.console import Console
from rich.table import Table
import time

# Configuration
HTB_API_TOKEN = os.environ.get('HTB_API_TOKEN')
if not HTB_API_TOKEN:
    print("[-] Erreur: La variable d'environnement HTB_API_TOKEN n'est pas définie")
    sys.exit(1)

# Headers pour les requêtes API
headers = {
    "Host": "labs.hackthebox.com",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Authorization": f"Bearer {HTB_API_TOKEN}",
    "Origin": "https://app.hackthebox.com",
    "Connection": "keep-alive",
    "Referer": "https://app.hackthebox.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site"
}

@dataclass
class HTBContent:
    name: str
    difficulty: str
    points: int
    status: str
    rating: float = 0.0
    solves: int = 0
    release_date: Optional[str] = None

class HTBDataFetcher:
    def __init__(self):
        self.console = Console()
        self.base_url = "https://www.hackthebox.com/api/v4"

    async def fetch_data(self, endpoint: str) -> List[Dict]:
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Debug: afficher la structure des données et l'URL
            print(f"\n[DEBUG] Requête vers: {url}")
            print(f"Status code: {response.status_code}")
            print(f"Type: {type(data)}")
            if isinstance(data, dict):
                print("Clés:", list(data.keys()))
                # Les challenges sont sous la clé 'challenges'
                if 'challenges' in data:
                    return data['challenges']
                # Pour les machines paginées
                elif 'data' in data and isinstance(data['data'], list):
                    return data
                # Pour les forteresses
                return data
            else:
                if data and isinstance(data, list):
                    print("Premier élément:", json.dumps(data[0], indent=2))
                return data
        except requests.exceptions.RequestException as e:
            self.console.print(f"[red][-] Erreur lors de la requête vers {endpoint}: {e}[/red]")
            return []

    def format_date(self, date_str: str) -> str:
        if not date_str:
            return "N/A"
        try:
            date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return date.strftime('%d/%m/%Y')
        except ValueError:
            return "N/A"

    def create_table(self, title: str, items: List[HTBContent]) -> Table:
        table = Table(title=title, show_header=True, header_style="bold magenta")
        table.add_column("Nom", style="cyan")
        table.add_column("Difficulté", style="green")
        table.add_column("Points", justify="right", style="yellow")
        table.add_column("État", style="blue")
        table.add_column("Note", justify="right", style="red")
        table.add_column("Résolutions", justify="right", style="green")
        table.add_column("Date de sortie", justify="center", style="blue")

        for item in sorted(items, key=lambda x: (-x.rating, x.name)):
            table.add_row(
                item.name,
                item.difficulty,
                str(item.points),
                item.status,
                f"{item.rating:.1f}/5.0" if item.rating else "N/A",
                str(item.solves) if item.solves else "N/A",
                self.format_date(item.release_date)
            )

        return table

    async def fetch_and_display_all(self):
        # Récupération des challenges
        self.console.print("\n[bold cyan]Récupération des challenges...[/bold cyan]")
        challenges_data = await self.fetch_data("challenge/list")
        challenges = []
        
        for c in challenges_data:
            if isinstance(c, dict):
                # Conversion des points en entier avec gestion des strings
                points_str = str(c.get('points', '0'))
                try:
                    points = int(points_str)
                except ValueError:
                    points = 0
                    
                challenges.append(HTBContent(
                    name=c.get('name', 'Inconnu'),
                    difficulty=f"{c.get('difficulty', 'Inconnu')} ({c.get('avg_difficulty', 0)}/100)",
                    points=points,
                    status='Retraité' if c.get('retired', False) else 'Actif',
                    rating=float(c.get('rating', 0)),
                    solves=c.get('solves', 0),
                    release_date=c.get('release_date')
                ))
        
        if challenges:
            self.console.print(self.create_table("Challenges HTB", challenges))
        else:
            self.console.print("[red]Aucun challenge trouvé ou format de données incorrect[/red]")

        # Attendre avant de passer aux machines
        time.sleep(2)

        # Récupération des machines
        self.console.print("\n[bold cyan]Récupération des machines...[/bold cyan]")
        machines = []
        page = 1
        
        while True:
            machines_data = await self.fetch_data(f"machine/paginated?retired=0&page={page}")
            
            # Vérifier la structure des données
            if not isinstance(machines_data, dict) or 'data' not in machines_data:
                print(f"[red]Structure de données invalide pour la page {page}[/red]")
                break
            
            # Traitement des machines de la page courante
            for m in machines_data['data']:
                if isinstance(m, dict):
                    try:
                        # Créer un tag pour les machines spéciales
                        tags = []
                        if m.get('is_competitive'):
                            tags.append('COMPETITIVE')
                        if m.get('labels'):
                            tags.extend(label['name'] for label in m['labels'])
                        status_parts = [m.get('os', 'Inconnu')]
                        if tags:
                            status_parts.append(f"[{', '.join(tags)}]")
                        status_parts.append('Gratuit' if m.get('free', False) else 'VIP')
                        
                        machines.append(HTBContent(
                            name=m.get('name', 'Inconnu'),
                            difficulty=f"{m.get('difficultyText', 'Inconnu')} ({m.get('difficulty', 0)}/100)",
                            points=int(m.get('points', 0)),
                            status=' - '.join(status_parts),
                            rating=float(m.get('star', 0)),
                            solves=m.get('user_owns_count', 0),
                            release_date=m.get('release')
                        ))
                    except (ValueError, TypeError) as e:
                        print(f"[red]Erreur lors du traitement de la machine {m.get('name', 'Inconnu')}: {e}[/red]")
                        continue
            
            print(f"[cyan]Page {page} traitée, {len(machines)} machines récupérées...[/cyan]")
            
            # Vérifier s'il y a une page suivante
            if not machines_data.get('links', {}).get('next'):
                break
                
            # Attendre un peu entre les pages
            time.sleep(1)
            page += 1
            
        if machines:
            self.console.print(self.create_table("Machines HTB", machines))
        else:
            self.console.print("[red]Aucune machine trouvée ou format de données incorrect[/red]")

        # Attendre avant de passer aux forteresses
        time.sleep(2)

        # Récupération des forteresses
        self.console.print("\n[bold cyan]Récupération des forteresses...[/bold cyan]")
        fortresses = []
        
        try:
            fortresses_data = await self.fetch_data("fortresses")
            
            if fortresses_data and isinstance(fortresses_data, dict) and 'data' in fortresses_data:
                for f in fortresses_data['data'].values():
                    if isinstance(f, dict):
                        fortresses.append(HTBContent(
                            name=f.get('name', 'Inconnu'),
                            difficulty=f"Drapeaux: {f.get('number_of_flags', 0)}",
                            points=f.get('id', 0),
                            status='Nouveau' if f.get('new', False) else 'Standard',
                            rating=0.0,
                            solves=0,
                            release_date=None
                        ))
        except Exception as e:
            self.console.print(f"[red]Erreur lors de la récupération des forteresses: {e}[/red]")
        
        if fortresses:
            self.console.print(self.create_table("Forteresses HTB", fortresses))
        else:
            self.console.print("[red]Aucune forteresse trouvée ou format de données incorrect[/red]")

    async def get_all_content(self) -> dict:
        """Récupère tout le contenu et le retourne sous forme de dictionnaire"""
        all_content = {
            'challenges': [],
            'machines': [],
            'fortresses': []
        }
        
        # Récupération des challenges
        challenges_data = await self.fetch_data("challenge/list")
        for c in challenges_data:
            if isinstance(c, dict):
                all_content['challenges'].append({
                    'id': str(c.get('id')),
                    'name': c.get('name', 'Inconnu'),
                    'difficulty': f"{c.get('difficulty', 'Inconnu')} ({c.get('avg_difficulty', 0)}/100)",
                    'points': int(str(c.get('points', '0')).strip() or '0'),
                    'status': 'Retraité' if c.get('retired', False) else 'Actif'
                })
        
        # Récupération des machines
        page = 1
        while True:
            machines_data = await self.fetch_data(f"machine/paginated?retired=0&page={page}")
            if not isinstance(machines_data, dict) or 'data' not in machines_data:
                break
                
            for m in machines_data['data']:
                if isinstance(m, dict):
                    try:
                        all_content['machines'].append({
                            'id': str(m.get('id')),
                            'name': m.get('name', 'Inconnu'),
                            'difficulty': f"{m.get('difficultyText', 'Inconnu')} ({m.get('difficulty', 0)}/100)",
                            'points': int(m.get('points', 0)),
                            'os': m.get('os', 'Inconnu'),
                            'free': m.get('free', False)
                        })
                    except (ValueError, TypeError):
                        continue
                        
            if not machines_data.get('links', {}).get('next'):
                break
            page += 1
            time.sleep(1)
        
        # Récupération des forteresses
        fortresses_data = await self.fetch_data("fortresses")
        if fortresses_data and isinstance(fortresses_data, dict) and 'data' in fortresses_data:
            for f in fortresses_data['data'].values():
                if isinstance(f, dict):
                    all_content['fortresses'].append({
                        'id': str(f.get('id')),
                        'name': f.get('name', 'Inconnu'),
                        'flags': f.get('number_of_flags', 0),
                        'new': f.get('new', False)
                    })
        
        return all_content

if __name__ == "__main__":
    import asyncio
    fetcher = HTBDataFetcher()
    asyncio.run(fetcher.fetch_and_display_all())
