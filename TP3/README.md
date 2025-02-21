# Sécurisation d'un VPS Debian avec Docker

## 1. Initialisation

1. **Connexion SSH**  
   Se connecter au VPS :
   ```bash
   ssh debian@remote_host
   ```
   *(Remplacez `remote_host` par l'IP ou le nom de domaine de votre VPS.)*

2. **Mise à jour du système**  
   Actualiser la liste des packages et appliquer les mises à jour :
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

3. **Installation d'outils essentiels**  
   Installer UFW (pare-feu) et Fail2ban (protection anti-brute force) :
   ```bash
   sudo apt install -y ufw fail2ban
   ```

4. **UFW avec Docker**  
   Installer et configurer ufw-docker pour gérer le mappage des ports Docker :
   ```bash
   sudo wget -O /usr/local/bin/ufw-docker https://github.com/chaifeng/ufw-docker/raw/master/ufw-docker
   sudo chmod +x /usr/local/bin/ufw-docker
   sudo ufw-docker install
   sudo systemctl restart ufw
   ```

## 2. Création d'un nouvel utilisateur

1. **Création de l'utilisateur**  
   Par exemple, créer l'utilisateur `simon` :
   ```bash
   sudo adduser simon
   ```

2. **Attribution des privilèges**  
   Accorder les droits sudo et l'accès à Docker :
   ```bash
   sudo usermod -aG sudo simon
   sudo usermod -aG docker simon
   ```

3. **Bloquer l'accès direct à l'utilisateur `debian` (optionnel)**  
   ```bash
   sudo passwd -l debian
   ```

## 3. Configuration des paires de clés SSH (sur Windows)

### a. Génération de la clé SSH

Dans `C:\Users\WindowsUsername\.ssh` :
```bash
ssh-keygen -t ed25519 -a 100
```
La clé publique est stockée dans `id_ed25519.pub`.

### b. Transfert de la clé vers le VPS

**Méthode 1 :**  
Utilisation de `ssh-copy-id` (la plus simple, si disponible) :
```bash
ssh-copy-id simon@remote_host
```

**Méthode 2 :**  
Utilisation de `cat` et SSH (plus fiable) :
```bash
cat ~/.ssh/id_ed25519.pub | ssh simon@remote_host "mkdir -p ~/.ssh && touch ~/.ssh/authorized_keys && chmod -R go= ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

**Méthode 3 :**  
Copie manuelle :
- Sur Windows, affichez et copiez la clé :
  ```bash
  type C:\Users\WindowsUsername\.ssh\id_ed25519.pub
  ```
- Sur le VPS (connecté en tant que simon) :
  ```bash
  mkdir -p ~/.ssh
  echo "public_key_string" >> ~/.ssh/authorized_keys
  chmod -R go= ~/.ssh
  ```
  *(Remplacez `public_key_string` par le contenu de votre clé publique.)*

> **Important :** Testez la connexion SSH avec l’utilisateur `simon` pour vérifier que l’authentification par clé fonctionne avant de désactiver l’authentification par mot de passe.

## 4. Sécurisation du service SSH

1. **Modifier `/etc/ssh/sshd_config`**  
   Ouvrez le fichier :
   ```bash
   sudo nano /etc/ssh/sshd_config
   ```
   Ajustez les paramètres suivants :
   ```
   Port {22000-29999}
   PasswordAuthentication no
   PermitRootLogin no
   ```
   *(Choisissez un port non standard dans la fourchette, par exemple `22022`.)*  
   Enregistrez et quittez (CTRL+X, Y, ENTER).

2. **Vérifier la configuration cloud-init**  
   Certains VPS utilisent cloud-init qui peut écraser vos paramètres SSH :
   ```bash
   sudo nano /etc/ssh/sshd_config.d/50-cloud-init.conf
   ```
   Assurez-vous que la ligne suivante est présente :
   ```
   PasswordAuthentication no
   ```

3. **Redémarrer SSH**  
   ```bash
   sudo systemctl restart ssh
   ```

> **Important :** Avant de fermer la session SSH initiale, ouvrez une nouvelle connexion dans un terminal différent pour tester la nouvelle configuration :
> ```bash
> ssh -p 22022 simon@remote_host
> ```

## 5. Configuration de UFW et Fail2Ban

1. **Configurer UFW**  
   Autoriser le port SSH choisi :
   ```bash
   sudo ufw allow 22022
   ```
   Vérifier les règles :
   ```bash
   sudo ufw status
   ```
   Puis activer UFW :
   ```bash
   sudo ufw enable
   ```

2. **Configurer Fail2Ban**  
   Copier et modifier la configuration :
   ```bash
   sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
   sudo nano /etc/fail2ban/jail.local
   ```
   Dans la section `[sshd]`, assurez-vous d'avoir :
   ```
   enabled = true
   port    = 22022
   ```
   Vérifiez ensuite le fichier de logs :
   ```bash
   ls -l /var/log/auth.log
   ```
   Si nécessaire, créez-le et ajustez les permissions :
   ```bash
   sudo touch /var/log/auth.log
   sudo chmod 640 /var/log/auth.log
   ```
   Redémarrez Fail2Ban :
   ```bash
   sudo systemctl restart fail2ban
   sudo fail2ban-client status sshd
   ```

## 6. Déploiement d'un site statique avec Docker

1. **Création du dossier du site**  
   ```bash
   mkdir website && cd website
   ```

2. **Création des fichiers**

   - **Fichier `docker-compose.yml` :**
     ```bash
     touch docker-compose.yml && nano docker-compose.yml
     ```
     Contenu :
     ```yaml
     services:
       web:
         image: nginx:latest
         container_name: mon-serveur-web
         ports:
           - "80:80"
         volumes:
           - ./index.html:/usr/share/nginx/html/index.html
         restart: always
     ```

   - **Fichier `index.html` :**
     ```bash
     touch index.html && nano index.html
     ```
     Contenu :
     ```html
     <!DOCTYPE html>
     <html>
       <head>
         <title>Hello World!</title>
       </head>
       <body>
         <h1>Hello World!</h1>
       </body>
     </html>
     ```

3. **Démarrage du service Docker**  
   ```bash
   docker compose up -d
   ```

## 7. Gestion des ports avec UFW et Docker

Docker modifie directement les règles iptables pour le mapping des ports, ce qui peut interférer avec UFW. Pour synchroniser les règles :

- **Autoriser un port**  
  Par exemple, pour le port 80 :
  ```bash
  sudo ufw-docker allow mon-serveur-web 80
  ```

- **Vérifier l'état de UFW**  
  ```bash
  sudo ufw status
  sudo ufw-docker status
  ```

## 8. Sources

- <https://help.ovhcloud.com/csm/fr-vps-security-tips?id=kb_article_view&sysparm_article=KB0047708#aller-plus-loin>
- <https://help.ovhcloud.com/csm/fr-dedicated-servers-creating-ssh-keys?id=kb_article_view&sysparm_article=KB0043385#ajout-de-cles-publiques-supplementaires-a-votre-serveur>
- <https://www.digitalocean.com/community/tutorials/how-to-set-up-ssh-keys-on-debian-11>
- <https://github.com/chaifeng/ufw-docker>
