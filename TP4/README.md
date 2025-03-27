# Sécurisation d'un DNS Public pour WoodyToys

## 1. Initialisation de l'environnement

```bash
# Création d'une structure organisée pour les fichiers de configuration
mkdir -p ~/dns-public/{config,zone}
cd ~/dns-public
```

## 2. Installation et configuration de Bind9

### 2.1 Test initial du container

```bash
# Lancement d'un container Bind pour vérifier la configuration de base
docker run -d --name=dns -p 53:53/udp -p 53:53/tcp internetsystemsconsortium/bind9:9.18
```

> **Résolution d'erreur de port**: Si vous rencontrez "unable to bind to port 53", vérifiez et désactivez les services utilisant ce port:
>
> ```bash
> sudo netstat -tulnp | grep :53
> sudo systemctl stop systemd-resolved
> sudo systemctl disable systemd-resolved
> ```

```bash
# Vérification du fonctionnement par défaut (mode récursif)
dig @localhost www.google.com

# Nettoyage du container de test
docker stop dns && docker rm dns
```

### 2.2 Configuration du serveur autoritaire

Créez le fichier de configuration principal:

```bash
# Création du fichier de configuration named.conf
cat > ~/dns-public/config/named.conf << 'EOF'
options {
  directory "/var/cache/bind";
  version "not currently available";
  allow-query { any; };
  allow-query-cache { none; };
  recursion no;
};

zone "m1-3.ephec-ti.be." {
  type master;
  file "/etc/bind/m1-3.zone";
  allow-transfer { none; };
};
EOF
```

Créez le fichier de zone:

```bash
# Création du fichier de zone
cat > ~/dns-public/zone/m1-3.zone << 'EOF'
; Zone file for m1-3.ephec-ti.be
$TTL 86400      ; 1 day
@       IN      SOA     ns.m1-3.ephec-ti.be. admin.m1-3.ephec-ti.be. (
                        2025022801      ; serial (YYYYMMDDNN)
                        21600           ; refresh (6 hours)
                        3600            ; retry (1 hour)
                        604800          ; expire (1 week)
                        86400           ; minimum TTL (1 day)
                        )
; Serveurs de noms
@       IN      NS      ns.m1-3.ephec-ti.be.

; Enregistrements A
@       IN      A       54.36.181.87    ; Adresse IP du domaine racine
ns      IN      A       54.36.181.87    ; Serveur DNS
www     IN      A       54.36.181.87    ; Site web
mail    IN      A       54.36.181.87    ; Serveur mail

; Enregistrement MX
@       IN      MX      10 mail.m1-3.ephec-ti.be.
EOF
```

### 2.3 Validation de la configuration

```bash
# Lancement du container avec les fichiers montés
docker run -d --name=dns \
  -p 53:53/udp -p 53:53/tcp \
  --mount type=bind,source=$(pwd)/config/named.conf,target=/etc/bind/named.conf \
  --mount type=bind,source=$(pwd)/zone/m1-3.zone,target=/etc/bind/m1-3.zone \
  internetsystemsconsortium/bind9:9.18

# Vérification de la syntaxe et du contenu
docker exec dns named-checkconf /etc/bind/named.conf
docker exec dns named-checkzone m1-3.ephec-ti.be /etc/bind/m1-3.zone

# Vérification du fonctionnement
dig @localhost ns.m1-3.ephec-ti.be
dig @localhost www.m1-3.ephec-ti.be
```

### 2.4 Création de l'image personnalisée

```bash
# Création du Dockerfile
cat > ~/dns-public/Dockerfile << 'EOF'
FROM internetsystemsconsortium/bind9:9.18

COPY config/named.conf /etc/bind/named.conf
COPY zone/m1-3.zone    /etc/bind/m1-3.zone

RUN chown -R bind:bind /etc/bind/

EXPOSE 53/udp 53/tcp

ENTRYPOINT ["/usr/sbin/named"]
CMD ["-g", "-c", "/etc/bind/named.conf", "-u", "bind"]
EOF
```

```bash
# Construction et déploiement
docker build -t dns-woodytoys .
docker stop dns && docker rm dns
docker run -d --name=dns -p 53:53/udp -p 53:53/tcp --restart=unless-stopped dns-woodytoys
```

### 2.5 Configuration pour faciliter les mises à jour

```bash
# Redéploiement avec le fichier de zone monté
docker stop dns && docker rm dns
docker run -d --name=dns \
  -p 53:53/udp -p 53:53/tcp \
  --restart=unless-stopped \
  --mount type=bind,source=$(pwd)/zone/m1-3.zone,target=/etc/bind/m1-3.zone \
  dns-woodytoys
```

## 3. Délégation de la zone DNS

### 3.1 Resource Records pour la délégation

Créez un fichier avec les informations de délégation:

```bash
# Création du fichier de délégation
cat > ~/dns-public/delegation_records.txt << 'EOF'
m1-3    IN    NS    ns.m1-3.ephec-ti.be.
ns.m1-3 IN    A     54.36.181.87
EOF
```

Envoyez ce fichier par email à Mme Van Den Schrieck.

### 3.2 Vérification de la délégation

```bash
# Vérification que la délégation a été correctement configurée
dig @ns110.ovh.net m1-3.ephec-ti.be NS

# Vérification du fonctionnement complet
ping www.m1-3.ephec-ti.be
```

### 3.3 Validation avec Zonemaster

Testez votre domaine sur [Zonemaster](https://www.zonemaster.net/) pour s'assurer qu'il respecte les bonnes pratiques DNS.

Résultats: <https://www.zonemaster.net/en/result/1f0f05858303f3fa>

## 4. Sécurisation avec DNSSEC

### 4.1 Activation de DNSSEC

```bash
# Mise à jour du fichier named.conf pour activer DNSSEC
cat > ~/dns-public/config/named.conf << 'EOF'
options {
  directory "/var/cache/bind";
  version "not currently available";
  allow-query { any; };
  allow-query-cache { none; };
  recursion no;
};

zone "m1-3.ephec-ti.be." {
  type master;
  inline-signing yes;
  dnssec-policy default;
  file "/etc/bind/m1-3.zone";
  allow-transfer {
    none;
  };
};
EOF
```

### 4.2 Déploiement de la configuration DNSSEC

```bash
# Reconstruction de l'image avec DNSSEC
docker build -t dns-woodytoys:dnssec .

# Création d'un volume pour les données DNSSEC
docker volume create dns-data

# Déploiement avec persistance des données DNSSEC
docker stop dns && docker rm dns
docker run -d --name=dns \
  -p 53:53/udp -p 53:53/tcp \
  --restart=unless-stopped \
  --mount type=bind,source=$(pwd)/zone/m1-3.zone,target=/etc/bind/m1-3.zone \
  --mount type=volume,source=dns-data,target=/var/cache/bind \
  dns-woodytoys:dnssec
```

### 4.3 Vérification des signatures DNSSEC

```bash
# Vérification des signatures sur les enregistrements
dig @localhost www.m1-3.ephec-ti.be +dnssec

# Récupération des clés DNSSEC
dig @localhost m1-3.ephec-ti.be DNSKEY
```

### 4.4 Génération du Record DS

```bash
# Accéder au container avec /bin/sh
docker exec -it dns /bin/sh

# Localiser et générer le DS record à partir de la clé KSK
ls -la /var/cache/bind/K*.key
dnssec-dsfromkey /var/cache/bind/Km1-3.ephec-ti.be.+013+02726.key
```

Résultat:

```bash
m1-3.ephec-ti.be. IN DS 2726 13 2 03D413D7AA02403EFB7D4FD7C0EDF34D720773ABBC458F3F30AA8BA94189C996
```

### 4.5 Test de la sécurisation DNSSEC

```bash
# Vérification avec dig d'un RR signé (noter le flag ad qui indique une validation réussie)
dig @1.1.1.1 +dnssec www.m1-3.ephec-ti.be

# Vérification de la présence du RRSIG dans la réponse
dig @localhost www.m1-3.ephec-ti.be +dnssec +multiline

# Vérification avec delv (utilitaire de validation DNSSEC)
delv @localhost www.m1-3.ephec-ti.be
```

Testez votre domaine sur [DNSViz](https://dnsviz.net/) pour visualisez la chaîne de confiance DNSSEC.

Résultats:

![résultats de l'analyse DNSViz](https://raw.githubusercontent.com/Simon-Fontaine/ADMIN-2TM1-3/refs/heads/main/TP4/m1-3.ephec-ti.be-2025-02-27-21_05_01-UTC.png)


### 5 Mise en place d'un DNS secondaire

## 5.1 Sur le serveur primaire

Il faut tout d'abord modifier le fichier `named.conf` qu'on a créer plus tôt. Il faut y indiquer les adresses ip du DNS secondaire. 


## 5.2 Sur le serveur secondaire

Pour créer un DNS secondaire, il faut créer un fichier `named.conf`. Ce fichier doit être configuré en tant que slave et pour le relier au DNS primaire il faut indiquer l'adresse IP du VPS où se trouve le DNS primaire.

```bash
options {
  directory "/var/cache/bind";
  version "not currently available";
  allow-query { any; };
  allow-query-cache { none; };
  recursion no;
  listen-on-v6 { any; };
  dnssec-validation auto;
};

zone "m1-3.ephec-ti.be." {
  type slave;
  file "/var/cache/bind/m1-3.zone";
  masters {
    54.36.181.87;  # IPv4 du primaire
    2001:41d0:302:2200::5e83;  # IPv6 du primaire
  };
  inline-signing no;
};
```




