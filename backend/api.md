# API Documentation - SIOU Application

## Table des matières
- [Authentification](#authentification)
- [Administration](#administration)
- [Chat](#chat)
- [Conversations](#conversations)
- [Documents](#documents)
- [Feedbacks](#feedbacks)

## Authentification

### POST `/api/auth/login`
- **Description**: Authentification de l'utilisateur
- **Utilisateur**: Tous les utilisateurs
- **Paramètres**: LoginRequest (username, password)
- **Retour**: AuthResponse (access_token, token_type, user)

### POST `/api/auth/refresh`
- **Description**: Rafraîchissement du token d'accès
- **Utilisateur**: Utilisateurs authentifiés
- **Paramètres**: RefreshRequest (refresh_token)
- **Retour**: AuthResponse

### POST `/api/auth/logout`
- **Description**: Déconnexion de l'utilisateur
- **Utilisateur**: Utilisateurs authentifiés

### GET `/api/auth/me`
- **Description**: Récupération des informations de l'utilisateur courant
- **Utilisateur**: Utilisateurs authentifiés
- **Retour**: UserSummary

### PATCH `/api/auth/me`
- **Description**: Mise à jour par l'utilisateur de son propre profil (self-service)
- **Utilisateur**: Utilisateurs authentifiés
- **Paramètres**: UserSelfUpdate (first_name, last_name) — le rôle et l'état actif ne sont **pas** modifiables ici
- **Retour**: UserSummary

## Administration

### GET `/api/admin/users`
- **Description**: Liste tous les utilisateurs
- **Utilisateur**: Administrateurs uniquement
- **Retour**: Liste de UserRead

### POST `/api/admin/users`
- **Description**: Création d'un nouvel utilisateur
- **Utilisateur**: Administrateurs uniquement
- **Paramètres**: UserCreate
- **Retour**: UserRead

### GET `/api/admin/users/{user_id}`
- **Description**: Récupération d'un utilisateur spécifique
- **Utilisateur**: Administrateurs uniquement
- **Retour**: UserRead

### PATCH `/api/admin/users/{user_id}`
- **Description**: Mise à jour d'un utilisateur
- **Utilisateur**: Administrateurs uniquement
- **Paramètres**: UserUpdate
- **Retour**: UserRead

### DELETE `/api/admin/users/{user_id}`
- **Description**: Suppression d'un utilisateur
- **Utilisateur**: Administrateurs uniquement

### GET `/api/admin/documents`
- **Description**: Liste tous les documents
- **Utilisateur**: Administrateurs uniquement
- **Retour**: Liste de DocumentRead

### POST `/api/admin/documents`
- **Description**: Création d'un nouveau document
- **Utilisateur**: Administrateurs uniquement
- **Paramètres**: DocumentCreate
- **Retour**: DocumentRead

### GET `/api/admin/documents/{document_id}`
- **Description**: Récupération d'un document spécifique
- **Utilisateur**: Administrateurs uniquement
- **Retour**: DocumentRead

### PATCH `/api/admin/documents/{document_id}`
- **Description**: Mise à jour d'un document
- **Utilisateur**: Administrateurs uniquement
- **Paramètres**: DocumentUpdate
- **Retour**: DocumentRead

### DELETE `/api/admin/documents/{document_id}`
- **Description**: Suppression d'un document
- **Utilisateur**: Administrateurs uniquement

### GET `/api/admin/feedbacks`
- **Description**: Liste tous les feedbacks
- **Utilisateur**: Administrateurs uniquement
- **Retour**: Liste de FeedbackRead

### GET `/api/admin/feedbacks/{feedback_id}`
- **Description**: Récupération d'un feedback spécifique
- **Utilisateur**: Administrateurs uniquement
- **Retour**: FeedbackRead

### DELETE `/api/admin/feedbacks/{feedback_id}`
- **Description**: Suppression d'un feedback
- **Utilisateur**: Administrateurs uniquement

## Chat

### POST `/api/chat`
- **Description**: Pose une question au système de chat
- **Utilisateur**: Utilisateurs authentifiés
- **Paramètres**: ChatRequest (question, conversation_id)
- **Retour**: ChatResponse (text, sources, confidence, model, conversation_id)

## Conversations

### GET `/api/conversations`
- **Description**: Liste les conversations de l'utilisateur courant
- **Utilisateur**: Utilisateurs authentifiés
- **Retour**: Liste de ConversationSummary

### GET `/api/conversations/{conversation_id}`
- **Description**: Récupération d'une conversation spécifique
- **Utilisateur**: Utilisateurs authentifiés
- **Retour**: ConversationSummary

### DELETE `/api/conversations/{conversation_id}`
- **Description**: Suppression d'une conversation
- **Utilisateur**: Utilisateurs authentifiés

### POST `/api/conversations`
- **Description**: Création d'une nouvelle conversation
- **Utilisateur**: Utilisateurs authentifiés
- **Paramètres**: ConversationCreate
- **Retour**: ConversationSummary

### PATCH `/api/conversations/{conversation_id}`
- **Description**: Mise à jour d'une conversation
- **Utilisateur**: Utilisateurs authentifiés
- **Paramètres**: ConversationUpdate
- **Retour**: ConversationSummary

## Documents

### GET `/api/documents`
- **Description**: Liste les documents disponibles
- **Utilisateur**: Utilisateurs authentifiés
- **Retour**: Liste de DocumentSummary

### POST `/api/documents`
- **Description**: Upload d'un nouveau document
- **Utilisateur**: Utilisateurs authentifiés
- **Paramètres**: DocumentCreate
- **Retour**: DocumentSummary

### GET `/api/documents/{document_id}`
- **Description**: Récupération d'un document spécifique
- **Utilisateur**: Utilisateurs authentifiés
- **Retour**: DocumentSummary

### PUT `/api/documents/{document_id}`
- **Description**: Mise à jour complète d'un document
- **Utilisateur**: Utilisateurs authentifiés
- **Paramètres**: DocumentUpdate
- **Retour**: DocumentSummary

### DELETE `/api/documents/{document_id}`
- **Description**: Suppression d'un document
- **Utilisateur**: Utilisateurs authentifiés

### POST `/api/documents/{document_id}/validate`
- **Description**: Validation d'un document
- **Utilisateur**: Utilisateurs avec droits de validation
- **Retour**: Message de confirmation

### POST `/api/documents/{document_id}/reject`
- **Description**: Rejet d'un document
- **Utilisateur**: Utilisateurs avec droits de validation
- **Retour**: Message de confirmation

### POST `/api/documents/{document_id}/chunks`
- **Description**: Ajout de chunks à un document
- **Utilisateur**: Utilisateurs authentifiés
- **Paramètres**: DocumentChunkCreate
- **Retour**: DocumentRead

## Feedbacks

### GET `/api/feedbacks`
- **Description**: Liste les feedbacks de l'utilisateur courant
- **Utilisateur**: Utilisateurs authentifiés
- **Retour**: Liste de FeedbackRead

### POST `/api/feedbacks`
- **Description**: Création d'un nouveau feedback
- **Utilisateur**: Utilisateurs authentifiés
- **Paramètres**: FeedbackCreate
- **Retour**: FeedbackRead

### GET `/api/feedbacks/{feedback_id}`
- **Description**: Récupération d'un feedback spécifique
- **Utilisateur**: Utilisateurs authentifiés
- **Retour**: FeedbackRead

### PATCH `/api/feedbacks/{feedback_id}`
- **Description**: Mise à jour d'un feedback
- **Utilisateur**: Utilisateurs authentifiés
- **Paramètres**: FeedbackUpdate
- **Retour**: FeedbackRead

### DELETE `/api/feedbacks/{feedback_id}`
- **Description**: Suppression d'un feedback
- **Utilisateur**: Utilisateurs authentifiés

## Statistiques

### GET `/api/stats`
- **Description**: Statistiques agrégées du tableau de bord (conversations du mois courant vs précédent, documents : total / récents / répartition par statut)
- **Utilisateur**: Utilisateurs authentifiés
- **Retour**: `{ conversations: { current_month, previous_month, change_percent }, documents: { total, recent, by_status: [{ status, label, count, percentage }] } }`