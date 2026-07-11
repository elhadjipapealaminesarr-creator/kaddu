# Kaddu — Vote confidentiel

Application de **vote secret et vérifiable** pour associations, coopératives,
tontines, syndicats et amicales. Chaque bulletin est **chiffré** avant d'être
enregistré ; le décompte est calculé **sur les bulletins chiffrés** (chiffrement
homomorphe de Paillier) et seul le total final est déchiffré. Personne — ni le
serveur, ni l'organisateur — ne peut lire un vote individuel.

C'est la version « simple » (sans blockchain) de l'idée portée par la technologie
Zama : calculer sur des données chiffrées sans jamais les révéler.

---

## Essayer en local (Windows)

1. Installer Python depuis https://www.python.org/downloads/ (cocher **Add Python to PATH**).
2. Double-cliquer sur **`start.bat`**.
3. Ouvrir le navigateur sur **http://localhost:5000**.

## Mettre en ligne (gratuit, Render)

1. Créer un compte sur https://github.com et sur https://render.com.
2. Déposer ce dossier `kaddu-vote` dans un dépôt GitHub.
3. Sur Render : **New +** → **Blueprint** → choisir le dépôt. Render lit `render.yaml`
   et déploie tout seul.
4. Garder l'app éveillée (plan gratuit) avec un monitor UptimeRobot sur `.../ping`
   (voir le guide fourni séparément).

---

## L'installer comme une app sur téléphone (PWA)

Kaddu est une **PWA** : une fois en ligne (https), on l'installe sans passer par un store.

- **Android (Chrome)** : ouvrir le lien → un bouton « Installer l'application » apparaît
  (ou menu ⋮ → « Ajouter à l'écran d'accueil »). L'icône Kaddu se pose sur le téléphone.
- **iPhone (Safari)** : ouvrir le lien → bouton Partager → « Sur l'écran d'accueil ».

Elle s'ouvre alors en plein écran, avec son icône, comme une vraie application.
Pour aller plus loin (Google Play), on emballe cette PWA en « TWA » (compte Google Play
Developer ~25 $ une fois). L'App Store d'Apple (~99 $/an + Mac) n'est utile que plus tard.

## Écrans

- `/` accueil · `/creer` créer un vote · `/partage/<id>` lien + QR à partager
- `/v/<id>` voter · `/r/<id>` résultat · `/admin/<id>?t=<jeton>` tableau de bord organisateur

## Ce qui est garanti (et ce qui ne l'est pas)

- **Garanti** : les bulletins sont illisibles dans la base ; même l'organisateur ne
  voit aucun vote individuel ; pendant le vote, aucun total n'est visible (juste le
  nombre de votants) ; le résultat n'apparaît qu'après clôture.
- **Limite honnête** : c'est la version « simple ». Il reste un point de confiance —
  la clé privée du vote est détenue par le serveur. Pour un « zéro confiance » total
  (personne ne peut tricher, même pas l'hébergeur), il faudrait la version blockchain
  fhEVM de Zama, plus lourde. Cette version simple est parfaite pour tester avec de
  vrais groupes et convient à la grande majorité des associations.

## Détails techniques

- Flask + SQLite, chiffrement `phe` (Paillier), QR code côté navigateur.
- Anti double-vote par cookie (suffisant pour un prototype ; une vraie liste de
  votants par jeton pourra être ajoutée ensuite).
- La base est un simple fichier `kaddu.db`. Sur Render gratuit, le disque est
  éphémère (réinitialisé à chaque redéploiement) ; pour conserver durablement les
  votes, brancher un PostgreSQL gratuit (Neon/Supabase) le moment venu.
