# Tableau de bord Or — V6.1

## Correctif principal

La V6 utilisait encore une page AuCOFFRE centrée sur le Napoléon pour tous les produits. Le parseur retrouvait alors des mots génériques présents dans la navigation et affichait une offre Napoléon sur le Souverain ou d’autres boutons.

La V6.1 affecte une page AuCOFFRE dédiée à chaque produit :

- Napoléon 20 F ;
- 20 F Suisse ;
- Souverain ;
- Maple Leaf 1 oz ;
- Krugerrand 1 oz ;
- Philharmonique 1 oz ;
- lingotins 20 g, 50 g et 100 g.

Lorsqu’aucune page fiable ou aucune offre n’est disponible, l’application l’indique au lieu de reprendre une offre d’un autre produit.

## Déploiement

Remplacer le contenu du dépôt par les fichiers de cette archive en conservant uniquement `.git`, puis commit et push.

Commit conseillé : `V6.1 - correction des sources AuCOFFRE par produit`
