# Sécurisation du service mail pour WoodyToys

## 1. Initialisation de l'environnement

```bash
# Création d'une structure organisée pour les fichiers de configuration
mkdir -p ~/mail-secure/docker-data/dms/{mail-data,mail-state,mail-logs,config}
cd ~/mail-secure
```

## 2. Configuration DNS pour le service mail

### 2.1. Mise à jour de la zone DNS

```bash
# Modification du fichier de zone DNS pour ajouter les entrées mail
cat > ~/dns-public/zone/m1-3.zone << 'EOF'
; Zone file for m1-3.ephec-ti.be
$TTL 86400      ; 1 day
@       IN      SOA     ns.m1-3.ephec-ti.be. admin.m1-3.ephec-ti.be. (
                        2025031401      ; serial (YYYYMMDD + version)
                        21600           ; refresh (6h)
                        3600            ; retry (1h)
                        1209600         ; expire (14d)
                        3600            ; minimum (1h)
                        )
; Serveurs de noms
@       IN      NS      ns.m1-3.ephec-ti.be.

; Enregistrements A
@       IN      A       54.36.181.87
ns      IN      A       54.36.181.87
www     IN      A       54.36.181.87
mail    IN      A       54.36.181.87
blog    IN      A       54.36.181.87

; Challenge Let's Encrypt
_acme-challenge IN TXT "TSp9x8JFmLa1MtSNWIdcPF_AEDhHDbUt7bj8O0IjVko"

; Enregistrement MX
@       IN      MX      10 mail.m1-3.ephec-ti.be.

; Enregistrement SPF (optimisé)
@       IN      TXT     "v=spf1 mx ip4:54.36.181.87 -all"

; Enregistrement DKIM
mail._domainkey IN      TXT     ( "v=DKIM1; h=sha256; k=rsa; "
          "p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2EAp9mXps45BVFRkAxjnB4CAChooVH2YNCah+jaX1JE+Ih75vAxcncHAAkXCAg5dcngB/CsoJJXo8ihvWXR4umW35OZV7X6LYKRyggZtF47Oum207LFUIex7tlScXhsGUCKpsG+9E548WBl5GoLKFHQlH5/97tXrOWWmhPJpXkjbVinheIFzTBgEO/x3iPw/B0ghigvbtWITfj"
          "PsuKmiLTivJ/6q6rQxiZQ3t9898p1p/nLsZEq3XmniJDHv4OFOYWmPMeoKHbGjVSfCjbalPghsOej81n2kJGGL/Yox7TqWwzTRytZiG8aD6MdCq1qlRyh5WcXlr3IdanObMynuCQIDAQAB" )

; Enregistrement DMARC
_dmarc  IN      TXT     "v=DMARC1; p=quarantine; sp=quarantine; adkim=s; aspf=s; pct=100; fo=1; rf=afrf; ri=86400; rua=mailto:postmaster@m1-3.ephec-ti.be; ruf=mailto:postmaster@m1-3.ephec-ti.be"

; Enregistrements CAA
@       IN      CAA     0 issue "letsencrypt.org"
@       IN      CAA     0 issuewild "letsencrypt.org"
@       IN      CAA     0 iodef "mailto:admin@m1-3.ephec-ti.be"

; Enregistrements TXT
@       IN      TXT     "v=TLSRPTv1; rua=mailto:admin@m1-3.ephec-ti.be"
EOF

# Redémarrer le service DNS pour appliquer les changements
cd ~/dns-public
docker restart dns

# Vérifier que les entrées DNS sont correctement configurées
dig @localhost mail.m1-3.ephec-ti.be
dig @localhost MX m1-3.ephec-ti.be
dig @localhost TXT m1-3.ephec-ti.be
```

### 2.2. Configuration du PTR record

Pour configurer le PTR record, il faut contacter le fournisseur du VPS (OVH dans notre cas).

```bash
# Identifier l'identifiant DNS du VPS
dig -x 54.36.181.87

# Le résultat devrait montrer un nom comme vps-0356fc47.vps.ovh.net
# 0356fc47 est l'identifiant DNS
```

Email à envoyer au responsable (enseignant) :

```txt
Objet : Demande de configuration PTR pour le serveur mail

Bonjour,

Dans le cadre du TP7, je souhaite configurer le PTR record pour mon serveur mail.
Voici les informations nécessaires :
- Identifiant DNS du VPS : 0356fc47
- Adresse IP : 54.36.181.87
- Nom souhaité pour le PTR : mail.m1-3.ephec-ti.be

Merci de votre aide.

Cordialement,
[Votre nom]
```

## 3. Mise en place du serveur mail

### 3.1. Récupération des fichiers du serveur mail

```bash
cd ~/mail-secure

# Téléchargement du script de configuration
wget https://raw.githubusercontent.com/docker-mailserver/docker-mailserver/master/setup.sh
chmod +x setup.sh
```

### 3.2. Configuration du fichier docker-compose

```bash
cat > compose.yaml << 'EOF'
services:
  mailserver:
    image: ghcr.io/docker-mailserver/docker-mailserver:latest
    container_name: mailserver
    hostname: mail.m1-3.ephec-ti.be
    env_file: mailserver.env
    ports:
      - "25:25"
      - "143:143"
      - "465:465"
      - "587:587"
      - "993:993"
    volumes:
      - ./docker-data/dms/mail-data/:/var/mail/
      - ./docker-data/dms/mail-state/:/var/mail-state/
      - ./docker-data/dms/mail-logs/:/var/log/mail/
      - ./docker-data/dms/config/:/tmp/docker-mailserver/
      - /etc/localtime:/etc/localtime:ro
      - web-secure_letsencrypt:/etc/letsencrypt:ro
    restart: always
    stop_grace_period: 1m
    healthcheck:
      test: "ss --listening --tcp | grep -P 'LISTEN.+:smtp' || exit 1"
      timeout: 3s
      retries: 0

volumes:
  web-secure_letsencrypt:
    external: true
EOF
```

### 3.3. Configuration des variables d'environnement

```bash
cat > mailserver.env << 'EOF'
# Configuration générale
OVERRIDE_HOSTNAME=mail.m1-3.ephec-ti.be
POSTMASTER_ADDRESS=postmaster@m1-3.ephec-ti.be
LOG_LEVEL=info
PERMIT_DOCKER=none
TZ=Europe/Brussels
ENABLE_UPDATE_CHECK=1

# Configuration sécurité anti-spoofing
SPOOF_PROTECTION=1
ENABLE_SRS=1

# Configuration de sécurité DKIM/DMARC
ENABLE_OPENDKIM=1
ENABLE_OPENDMARC=1
ENABLE_POLICYD_SPF=1

# Configuration des services
ENABLE_IMAP=1
ENABLE_POP3=0
ENABLE_CLAMAV=0
ENABLE_AMAVIS=1
SMTP_ONLY=0

# Configuration SSL/TLS
SSL_TYPE=letsencrypt
SSL_CERT_PATH=/etc/letsencrypt/live/m1-3.ephec-ti.be/fullchain.pem
SSL_KEY_PATH=/etc/letsencrypt/live/m1-3.ephec-ti.be/privkey.pem
TLS_LEVEL=modern

# Configuration Postscreen pour protection contre les attaques
POSTSCREEN_ACTION=enforce

# Configuration SpamAssassin
ENABLE_SPAMASSASSIN=1
SPAMASSASSIN_SPAM_TO_INBOX=1
MOVE_SPAM_TO_JUNK=1
MARK_SPAM_AS_READ=0
SA_TAG=2.0
SA_TAG2=6.31
SA_KILL=10.0

# Configuration quotas
ENABLE_QUOTAS=1
POSTFIX_MESSAGE_SIZE_LIMIT=15728640  # 15MB

# Configuration Fail2Ban
ENABLE_FAIL2BAN=1
FAIL2BAN_BLOCKTYPE=drop

# Restrictions Postfix supplémentaires
POSTFIX_REJECT_UNKNOWN_CLIENT_HOSTNAME=1

# Configuration ports et protocoles
POSTFIX_INET_PROTOCOLS=all
DOVECOT_INET_PROTOCOLS=all
EOF
```

### 3.4. Démarrage du serveur mail

```bash
# Lancement du container
docker compose up -d

# Vérification du démarrage
docker logs -f mailserver
```

### 3.5. Création des comptes utilisateurs et aliases

```bash
# Création des comptes utilisateurs
./setup.sh email add admin@m1-3.ephec-ti.be
# Entrez un mot de passe sécurisé quand demandé

./setup.sh email add test@m1-3.ephec-ti.be
# Entrez un mot de passe sécurisé quand demandé

# Ajout d'un alias pour postmaster
./setup.sh alias add postmaster@m1-3.ephec-ti.be admin@m1-3.ephec-ti.be

# Vérification des comptes créés
./setup.sh email list
```

## 4. Sécurisation du service mail

### 4.1. Génération et configuration des clés DKIM

```bash
# Génération des clés DKIM
./setup.sh config dkim

# Vérification que les clés ont été correctement générées
ls -la docker-data/dms/config/opendkim/keys/m1-3.ephec-ti.be/

# Affichage de la clé publique DKIM pour l'ajouter dans la zone DNS
cat docker-data/dms/config/opendkim/keys/m1-3.ephec-ti.be/mail.txt

# La clé est déjà configurée dans notre zone DNS depuis l'étape 2.1
```

### 4.2. Authentification du domaine

Notre configuration DNS inclut déjà tous les éléments nécessaires pour l'authentification du domaine:

1. **SPF** : `v=spf1 mx ip4:54.36.181.87 -all`
   - Indique que seul le serveur MX et l'adresse IP spécifiée sont autorisés à envoyer des emails

2. **DKIM** : Enregistrement `mail._domainkey` avec la clé publique
   - Permet aux autres serveurs de vérifier la signature DKIM de nos emails

3. **DMARC** : `v=DMARC1; p=quarantine; sp=quarantine; adkim=s; aspf=s; pct=100; fo=1; rf=afrf; ri=86400; rua=mailto:postmaster@m1-3.ephec-ti.be; ruf=mailto:postmaster@m1-3.ephec-ti.be`
   - Politique DMARC strict avec rapports envoyés au postmaster

Vérification des enregistrements DNS:

```bash
# Vérification SPF
dig @localhost TXT m1-3.ephec-ti.be | grep "v=spf1"

# Vérification DKIM
dig @localhost TXT mail._domainkey.m1-3.ephec-ti.be | grep "v=DKIM1"

# Vérification DMARC
dig @localhost TXT _dmarc.m1-3.ephec-ti.be | grep "v=DMARC1"
```

### 4.3. Filtrage du spam avec SpamAssassin

SpamAssassin est déjà configuré dans notre fichier `mailserver.env` :

- `ENABLE_SPAMASSASSIN=1` : Active SpamAssassin
- `SA_TAG=2.0` : Marque les emails à partir d'un score de 2.0
- `SA_TAG2=6.31` : Ajoute les en-têtes "spam détecté" à partir d'un score de 6.31
- `SA_KILL=10.0` : Rejette les emails avec un score supérieur à 10.0
- `MOVE_SPAM_TO_JUNK=1` : Déplace automatiquement les spams dans le dossier Junk

Pour tester SpamAssassin, nous pouvons envoyer un email contenant le texte GTUBE :

```bash
# Texte GTUBE à inclure dans un email pour tester SpamAssassin
echo "XJS*C4JDBQADN1.NSBN3*2IDNEN*GTUBE-STANDARD-ANTI-UBE-TEST-EMAIL*C.34X"
```

### 4.4. Analyse du chiffrement TLS

```bash
# Vérification du support TLS pour SMTP
openssl s_client -connect mail.m1-3.ephec-ti.be:465 -servername mail.m1-3.ephec-ti.be </dev/null | grep -A 2 "issuer\|subject"

# Vérification du support TLS pour IMAP
openssl s_client -connect mail.m1-3.ephec-ti.be:993 -servername mail.m1-3.ephec-ti.be </dev/null | grep -A 2 "issuer\|subject"

# Liste des protocoles TLS et chiffrements supportés
nmap --script ssl-enum-ciphers -p 465,993 mail.m1-3.ephec-ti.be
```

Notre serveur mail utilise les ports suivants :

- **SMTP** :
  - Port 25 : SMTP standard (avec STARTTLS)
  - Port 587 : SMTP soumission (avec STARTTLS)
  - Port 465 : SMTP sécurisé (TLS implicite)
- **IMAP** :
  - Port 143 : IMAP standard (avec STARTTLS)
  - Port 993 : IMAPS (TLS implicite)

Pour une sécurité optimale, nous recommandons d'utiliser les ports TLS implicites (465 et 993).

## 5. Test et vérification finale

### 5.1. Tests avec MXToolbox

Vérifiez votre configuration avec MXToolbox :

1. Accédez à <https://mxtoolbox.com/SuperTool.aspx>
2. Entrez `mail.m1-3.ephec-ti.be` et sélectionnez "SMTP Test"
3. Vérifiez également:
   - SPF Lookup
   - DKIM Lookup
   - DMARC Lookup
   - Blacklist Check

### 5.2. Tests avec DKIMValidator

Vérifiez la signature DKIM et les scores de spam:

1. Accédez à <https://dkimvalidator.com/>
2. Envoyez un email à l'adresse fournie
3. Vérifiez les résultats de l'analyse

### 5.3. Test d'envoi et réception d'emails

#### Configuration du client mail (Thunderbird)

1. **Configuration du compte entrant (IMAP)**:
   - Serveur: mail.m1-3.ephec-ti.be
   - Port: 993
   - Sécurité: SSL/TLS
   - Méthode d'authentification: Mot de passe normal

2. **Configuration du compte sortant (SMTP)**:
   - Serveur: mail.m1-3.ephec-ti.be
   - Port: 465
   - Sécurité: SSL/TLS
   - Méthode d'authentification: Mot de passe normal

#### Tests à effectuer

1. **Test interne**: Envoi d'un email de <admin@m1-3.ephec-ti.be> à <test@m1-3.ephec-ti.be>
2. **Test externe**: Envoi d'un email vers une adresse Gmail ou autre service externe
3. **Test de réception**: Demander à quelqu'un d'envoyer un email à <admin@m1-3.ephec-ti.be>

```bash
# Vérification des logs pour suivre les tests
docker logs -f mailserver
```
