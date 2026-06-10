# Infrastructure DevOps HumaNai Platform

Ce répertoire contient l'ensemble des configurations infrastructure, conteneurs et scripts d'initialisation pour le projet **HumaNai** (Plateforme IA RH — YDAYS 2026).

---

## 1. Description des Services et Ports

Le fichier `docker-compose.yml` orchestre la stack technique suivante :

| Service | Technologie | Port Externe | Description |
| :--- | :--- | :--- | :--- |
| **postgres** | PostgreSQL 16 (pgvector) | `5432` | Base de données relationnelle et base vectorielle pour le RAG |
| **redis** | Redis 7 (Alpine) | `6379` | Cache, limiteur de requêtes (Rate-Limiter) et gestionnaire de tâches (BullMQ) |
| **minio** | MinIO (S3-compatible) | `9000` / `9001` | Stockage d'objets (documents générés et archives) |
| **nginx** | Nginx (Alpine) | `80` | Reverse proxy central de l'infrastructure |
| **prometheus**| Prometheus | `9090` | Collecteur de métriques système |
| **grafana** | Grafana | `3001` | Dashboarding de supervision (mot de passe admin configuré via `.env`) |

---

## 2. Démarrage et Utilisation (Makefile)

Un ensemble de commandes simplifiées est proposé via le `Makefile` à la racine de ce répertoire :

- **Lancement complet des services** :
  ```bash
  make up
  ```
- **Arrêt de l'infrastructure** :
  ```bash
  make down
  ```
- **Visualisation des logs** :
  ```bash
  make logs
  ```
- **Réinitialisation complète de la base de données** (supprime et recrée les volumes) :
  ```bash
  make reset-db
  ```
- **Peuplement de la base de données de développement** (Seed initial) :
  ```bash
  make seed
  ```
- **Exécution des tests unitaires et d'intégration** :
  ```bash
  make test
  ```

---

## 3. Sécurité & RLS (Row-Level Security)

Les scripts d'initialisation sous `postgres/init/` s'exécutent automatiquement dans l'ordre alphabétique :
1. `00_extensions.sql` : Active les extensions PG nécessaires (`uuid-ossp`, `pgcrypto`, `vector`, `pg_trgm`).
2. `01_schema.sql` : Définit les types personnalisés (enums), l'ensemble des tables relationnelles, les contraintes et index.
3. `02_rls.sql` : Active la sécurité RLS sur les tables sensibles (`users`, `employees`, `absences`, `generated_documents`, `annual_reviews`, `audit_logs`). Elle compare les variables de session `app.current_user_id` et `app.current_user_role` avec les colonnes de données pour restreindre l'accès en fonction des rôles utilisateur.
4. `03_seed.sql` : Injecte les données de démonstration (sites, départements, postes, utilisateurs factices avec UIDs Firebase et employés associés).

---

## 4. Rôles et Custom Claims Firebase

Le script `firebase/set-custom-claims.js` permet d'attribuer les rôles applicatifs aux comptes Firebase Auth via le SDK Admin.

### Configuration
1. Exportez le chemin vers le fichier JSON de votre clé de compte de service Firebase :
   ```bash
   export FIREBASE_SERVICE_ACCOUNT_KEY_PATH="/chemin/vers/cle-service-account.json"
   ```
2. Installez les dépendances :
   ```bash
   npm install firebase-admin
   ```

### Attribution d'un rôle
Exécutez le script en passant le UID de l'utilisateur et son rôle cible :
```bash
node set-custom-claims.js <firebase_uid> <role>
```
*Rôles valides : `collaborateur`, `manager`, `rh`, `direction`, `admin`, `qvt`*
