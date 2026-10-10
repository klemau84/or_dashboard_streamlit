# Comparateur d'or physique — V7.1

Remplacez les fichiers de votre dépôt par ceux de cette archive, sans supprimer `.git`.

Démarrage : `pip install -r requirements.txt` puis `streamlit run app.py`.

## V7.1
- Page de comparaison principale : quatre vendeurs identifiés, deux cartes par ligne.
- Sélection du produit et scénario livraison / stockage.
- Les autres offres AuCOFFRE sont reléguées aux détails.
- Une offre non livrable ou dont la livrabilité n'est pas confirmée n'est pas présentée comme livrable.
- GOLD AVENUE : aucun prix direct n'est inventé. Compléter le prix depuis le panier ; les prix stockés ne doivent pas être confondus avec les prix livrés.
- Un total livré n'est calculé que si le transport est renseigné ou confirmé gratuit.
- Frais de garde et frais de livraison restent des hypothèses configurables, et le classement est explicitement incomplet quand des données manquent.

Les prix et disponibilités ne sont pas des offres fermes. Vérifiez les paniers vendeurs avant tout achat.
