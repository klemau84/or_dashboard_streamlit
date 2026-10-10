from __future__ import annotations
from zoneinfo import ZoneInfo
import streamlit as st
from services.data import PRODUCTS, load_product_snapshot, GODOT_NAPOLEON_URL, GOLDFR_NAPOLEON_URL

st.set_page_config(page_title='Comparateur d’or physique — V7.1', page_icon='🟡', layout='wide')

def eur(x):
    return 'À confirmer' if x is None else f'{x:,.2f} €'.replace(',', ' ').replace('.', ',')

def pct(x):
    return 'ND' if x is None else f'{x:+.2f} %'.replace('.', ',')

@st.cache_data(ttl=300, show_spinner=False)
def collect(key):
    return load_product_snapshot(key)

if 'product' not in st.session_state:
    st.session_state.product='napoleon'

st.title('Comparateur d’or physique')
st.caption('Comparer les vendeurs, pas leurs catalogues. Prix détectés indicatifs ; le panier final fait foi.')
st.subheader('1. Choisir le produit')
cols=st.columns(3)
for i,p in enumerate(PRODUCTS):
    active=st.session_state.product==p.key
    if cols[i%3].button(('✓ ' if active else '')+p.label,key='p_'+p.key,type='primary' if active else 'secondary',use_container_width=True):
        st.session_state.product=p.key
        st.rerun()

p=next(x for x in PRODUCTS if x.key==st.session_state.product)
if p.key=='napoleon':
    mode=st.radio('2. Ton projet', ['Livraison immédiate', 'Achats progressifs, puis livraison'],horizontal=True)
    qty=st.number_input('Nombre de pièces',min_value=1,max_value=100,value=3 if mode=='Livraison immédiate' else 10,step=1)
    months=0 if mode=='Livraison immédiate' else st.slider('Durée de stockage (mois)',1,60,24)
else:
    mode=st.radio('2. Ton projet',['Livraison immédiate','Stockage, puis livraison'],horizontal=True)
    qty=st.number_input('Nombre de produits',min_value=1,max_value=100,value=1,step=1)
    months=0 if mode=='Livraison immédiate' else st.slider('Durée de stockage (mois)',1,60,24)

if st.button('Actualiser les données'):
    st.cache_data.clear()
    st.rerun()

with st.spinner('Collecte des prix publics…'):
    s=collect(p.key)
st.caption(f'{p.label} · {p.fine_gold_g:.4f} g d’or fin par unité · valeur métallique indicative : {eur(s.theoretical_value)} · collecte : {s.timestamp.astimezone(ZoneInfo("Europe/Paris")):%d/%m/%Y %H:%M}')
st.info('Une offre sans confirmation « Livrable : Oui » ne figure pas comme prix livrable. Les frais de livraison non vérifiés ne sont jamais supposés gratuits.')

# All values may be entered/overridden without confusing them with collected prices.
vendors=['GOLD AVENUE','Godot & Fils','AuCOFFRE','Gold.fr']
urls={
 'GOLD AVENUE':'https://www.goldavenue.com/fr',
 'Godot & Fils':GODOT_NAPOLEON_URL,
 'AuCOFFRE':p.aucoffre_urls[0],
 'Gold.fr':GOLDFR_NAPOLEON_URL,
}
coffre_candidates=[o for o in s.aucoffre_offers if (o.livrable or '').strip().lower()=='oui' and not o.is_lsp]
coffre_candidates.sort(key=lambda x:x.price)
coffre=coffre_candidates[0] if coffre_candidates else None
observed={
 'GOLD AVENUE':None,
 'Godot & Fils':s.godot.price if s.godot and p.key=='napoleon' else None,
 'AuCOFFRE':coffre.price if coffre else None,
 'Gold.fr':s.goldfr.price if s.goldfr and p.key=='napoleon' else None,
}

st.subheader('3. Comparer les quatre vendeurs')
st.caption('Les prix automatiques sont signalés comme tels. Les prix saisis manuellement ne sont pas des cotations en direct.')
with st.expander('Configurer les frais et compléter les prix manquants',expanded=False):
    st.write('Laisse un prix à zéro pour utiliser la cotation détectée. Une livraison à zéro n’est prise en compte comme gratuite que si tu coches « Livraison gratuite confirmée ».')
    manual={}
    for name in vendors:
        st.markdown('**'+name+'**')
        c=st.columns(5)
        price=c[0].number_input('Prix unitaire manuel (€)',0.0,1000000.0,0.0,step=1.0,key='manual_'+name)
        fee=c[1].number_input('Frais achat (%)',0.0,30.0,0.5 if name=='AuCOFFRE' else 0.0,step=0.1,key='fee_'+name)
        custody=c[2].number_input('Garde / mois (€)',0.0,1000.0,5.0 if name=='AuCOFFRE' else 0.0,step=1.0,key='cust_'+name)
        delivery=c[3].number_input('Livraison totale (€)',0.0,10000.0,0.0,step=5.0,key='delivery_'+name)
        free=c[4].checkbox('Livraison gratuite confirmée',value=False,key='free_'+name)
        manual[name]=(price,fee,custody,delivery,free)

cards=st.columns(2)
results=[]
for i,name in enumerate(vendors):
    override,fee,custody,delivery,free=manual[name]
    unit=override if override>0 else observed[name]
    source='Saisie manuelle' if override>0 else ('Prix public détecté' if unit is not None else 'Aucune cotation fiable')
    if name=='AuCOFFRE' and override<=0 and coffre is None:
        source='Aucune offre livrable confirmée'
    metal=s.theoretical_value
    premium=((unit/metal)-1)*100 if unit is not None and metal else None
    entry=unit*qty*(1+fee/100) if unit is not None else None
    guard=months*custody if entry is not None else None
    delivery_known=free or delivery>0
    total=entry+guard+(0 if free else delivery) if entry is not None and delivery_known else None
    if total is not None:results.append((name,total))
    with cards[i%2]:
        with st.container(border=True):
            st.markdown('### '+name)
            st.caption(source)
            a,b=st.columns(2)
            a.metric('Prix unitaire',eur(unit))
            b.metric('Prime sur métal',pct(premium))
            a,b=st.columns(2)
            a.metric(f'Achat de {qty} unité(s), frais inclus',eur(entry))
            b.metric('Coût total livré',eur(total))
            if entry is not None:
                st.caption(f'Garde estimée : {eur(guard)} · Livraison : '+('offerte (confirmée)' if free else eur(delivery) if delivery>0 else 'à confirmer'))
            else:
                st.caption('Prix non disponible : aucun total calculé.')
            st.markdown(f'[Voir la fiche du vendeur]({urls[name]})')
            if name=='AuCOFFRE':
                st.caption(f'{len(coffre_candidates)} offre(s) livrable(s) standard détectée(s). Les offres non livrables et LSP sont exclues du prix principal.')

if results:
    winner=min(results,key=lambda x:x[1])
    st.success(f'Meilleur total **calculable** : {winner[0]} — {eur(winner[1])}. Classement incomplet si des livraisons ou prix restent à confirmer.')
else:
    st.warning('Aucun coût total livré vérifiable pour le moment. Complète les frais de livraison depuis les paniers.')

with st.expander('Voir les autres offres AuCOFFRE (détails)',expanded=False):
    if not s.aucoffre_offers:
        st.write('Aucune offre fiable détectée.')
    else:
        st.caption('Ces offres sont uniquement celles d’AuCOFFRE, pas celles des quatre vendeurs.')
        for offer in s.aucoffre_offers[:30]:
            st.write(f'{eur(offer.price)} · {offer.product_name[:110]} · Livrable : {offer.livrable or "non confirmé"} · LSP : {"oui" if offer.is_lsp else "non"}')

with st.expander('Méthode et limites'):
    st.write('La valeur métallique utilise une référence PAXG/USDT convertie en EUR : ce n’est pas une cotation officielle de l’or spot. Les prix publics peuvent être différés ou non fermes.')
    st.write('Le coût de garde est une hypothèse mensuelle constante ; pour des achats progressifs, elle peut surestimer le coût réel. AuCOFFRE : vérifier le plancher de facturation, le statut LSP et les conditions de livraison. GOLD AVENUE : distinguer prix stocké et prix livré, et vérifier les frais de retrait et de transport Suisse–France.')
    st.write('La comparaison ne comprend ni fiscalité personnelle ni revente. Une offre sans prix ou frais confirmés ne peut pas être déclarée moins chère.')
    if s.errors:
        st.write('Diagnostics des sources :')
        for error in s.errors:st.caption(error)
