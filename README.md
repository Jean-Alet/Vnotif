# Vnotif

Vnotif est un moniteur Instagram en Python qui surveille des comptes de clubs de volleyball et envoie une notification push via **ntfy.sh** dès qu'un post d'annonce de tournoi est détecté.

Conçu pour tourner en continu sur un **Raspberry Pi**, sans connexion Instagram, sans navigateur.

> **Pourquoi ce projet ?** Les annonces de tournois de volley passent quasi-exclusivement par Instagram. Plutôt que d'activer les notifications pour tous les posts de tous les clubs — ou de checker manuellement leurs comptes — Vnotif surveille à ta place et ne t'alerte que quand un tournoi est annoncé.

**Auteur :** Alet Jean  
**Licence :** CC BY-NC 4.0

---

## Ce que fait le projet

Le script surveille en boucle une liste de comptes Instagram. À chaque cycle :

1. Il récupère le dernier post de chaque compte via l'endpoint JSON interne d'Instagram (`?__a=1`), avec fallback sur le scraping HTML en cas d'échec.
2. Il compare l'identifiant du post à l'état sauvegardé localement (`etat.json`).
3. Si le post est nouveau **et** contient un mot-clé de tournoi, une notification push urgente est envoyée sur le topic ntfy.sh configuré.
4. Les liens d'inscription détectés dans la légende (URLs, bit.ly, linktr.ee) sont extraits et inclus dans la notification.

La vérification tourne toutes les **3 minutes**. En cas de rate-limiting Instagram (HTTP 429), le script marque une pause automatique de 10 à 12 minutes.

---

## Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| Scraping JSON | Appel à `/?__a=1&__d=dis` avec headers imitant Chrome/Linux |
| Fallback HTML | Parsing de `window._sharedData` ou extraction du shortcode brut |
| Détection de tournoi | Comparaison insensible à la casse sur une liste de mots-clés FR/EN |
| Extraction de liens | Regex sur URLs, bit.ly et linktr.ee dans la légende du post |
| Notification push | Envoi via ntfy.sh avec titre, priorité urgente, tag et lien cliquable |
| Persistance d'état | Sauvegarde JSON du dernier post vu par compte |
| Gestion du rate-limit | Pause automatique + reprise sans crash |
| Logging | Fichier `monitor.log` + sortie console horodatée |

### Mots-clés surveillés

`tournoi` · `tournament` · `inscription` · `inscriptions` · `open` · `competition` · `registration` · `places disponibles` · `places limitées` · `s'inscrire` · `inscrivez-vous` · `sign up` · `signup`

---

## Structure du projet

```
vnotif/
├── monitor.py      # Boucle principale — scraping, détection, orchestration
├── notifier.py     # Envoi de la notification via ntfy.sh
├── comptes.txt     # Liste des comptes Instagram à surveiller
├── etat.json       # Dernier post vu par compte (généré automatiquement)
├── monitor.log     # Journal d'exécution (généré automatiquement)
└── requirements.txt
```

---

## Prérequis

- Python 3.10 ou supérieur
- Un topic [ntfy.sh](https://ntfy.sh) (gratuit, sans compte)
- L'application ntfy installée sur le téléphone (ou tout client compatible)
- Recommandé : Raspberry Pi ou toute machine qui tourne en continu

---

## Installation

```bash
# Cloner le dépôt
git clone https://github.com/Jean-Alet/vnotif.git
cd vnotif

# Installer les dépendances
pip install -r requirements.txt
```

---

## Configuration

### 1. Comptes à surveiller — `comptes.txt`

Un compte par ligne, avec ou sans `@`. Les lignes commençant par `#` sont ignorées.

```
# clubs volley Toulouse
@tacvb31
volffonsorbes
muretvolley
```

### 2. Topic ntfy.sh — `notifier.py`

Modifiez les deux constantes en haut du fichier :

```python
NTFY_TOPIC  = "votre-topic-secret"   # choisissez un nom unique et difficile à deviner
NTFY_SERVER = "https://ntfy.sh"      # ou votre instance auto-hébergée
```

Abonnez-vous ensuite à ce topic dans l'application ntfy sur votre téléphone.

### 3. Intervalle de vérification — `monitor.py` *(optionnel)*

```python
CHECK_INTERVAL = 3 * 60   # secondes entre deux cycles (défaut : 3 min)
```

---

## Utilisation

```bash
python monitor.py
```

Le script tourne indéfiniment. Sur Raspberry Pi, vous pouvez le lancer en arrière-plan avec `nohup` ou en service `systemd` :

```bash
# Lancement simple en arrière-plan
nohup python monitor.py &

# Consulter les logs en direct
tail -f monitor.log
```

### Exemple de sortie console

```
2025-05-20 08:00:01 [INFO] Monitor demarre. Intervalle : 3 min.
2025-05-20 08:00:03 [INFO] Verification de 7 compte(s)...
2025-05-20 08:00:04 [INFO]   @tacvb31
2025-05-20 08:00:05 [INFO]   Aucun nouveau post.
2025-05-20 08:00:10 [INFO]   @muretvolley
2025-05-20 08:00:11 [INFO]   Tournoi detecte chez @muretvolley
2025-05-20 08:00:11 [INFO] Notification envoyee.
```

### Exemple de notification reçue

```
Tournoi @muretvolley
Tournoi chez @muretvolley
https://linktr.ee/muretvolley
```

---

## Licence

Ce projet est distribué sous licence **CC BY-NC 4.0** (Creative Commons Attribution — Pas d'Utilisation Commerciale).

Vous êtes autorisé à :
- Consulter, utiliser et partager ce projet à des fins personnelles ou académiques
- Adapter le code pour un usage privé ou éducatif

Sous les conditions suivantes :
- **Attribution** — Vous devez créditer l'auteur (Alet Jean) et indiquer si des modifications ont été apportées
- **Pas d'utilisation commerciale** — Ce projet ne peut pas être utilisé à des fins commerciales ou lucratives

Toute utilisation en dehors de ces conditions nécessite une autorisation écrite préalable de l'auteur.
