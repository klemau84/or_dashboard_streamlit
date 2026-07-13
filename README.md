# Tableau de bord Or — Streamlit

Application Streamlit autonome pour comparer le Napoléon 20 francs entre :

- Binance : PAXG/USDT et EUR/USDT ;
- Godot & Fils : prix d'achat, cotation, intrinsèque et prime ;
- Gold.fr / Comptoir National de l'Or : cours Napoléon, prime et once EUR.

## Installation locale

```bash
git clone <URL_DU_DEPOT>
cd or_dashboard_streamlit
python -m venv .venv
source .venv/bin/activate
# Windows : .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Publication sur GitHub

```bash
git init
git add .
git commit -m "Initial Streamlit gold dashboard"
git branch -M main
git remote add origin <URL_DU_DEPOT>
git push -u origin main
```

## Déploiement sur Streamlit Community Cloud

1. Connecter GitHub à Streamlit Community Cloud.
2. Sélectionner le dépôt et la branche `main`.
3. Indiquer `app.py` comme fichier principal.
4. Déployer.

Aucune clé API n'est nécessaire : seules des données publiques sont utilisées.

## Structure

```text
.
├── app.py
├── requirements.txt
├── services/
│   ├── __init__.py
│   ├── data.py
│   ├── http.py
│   └── parsers.py
└── .streamlit/
    └── config.toml
```

## Fonctionnement

- Cache Streamlit de 5 minutes pour limiter les appels réseau.
- Bouton d'actualisation manuelle.
- Gestion des erreurs par source : si un site change, le reste du tableau continue de fonctionner.
- Calcul automatique de la valeur théorique du Napoléon 20F à partir de 5,805 g d'or fin.

## Avertissement

Ce tableau de bord est informatif et ne constitue pas un conseil financier.
