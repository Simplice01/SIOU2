# Guide Pratique : Réutilisation des Tokens et Envoi de Requêtes

## 🔑 Comprendre le Flux des Tokens

### 1. **Cycle de vie d'un token**
```
1. Connexion (POST /auth/login) → Obtient access_token + refresh_token
2. Requêtes API → Utilise access_token dans Authorization: Bearer
3. Token expiré → Utilise refresh_token pour obtenir nouveau access_token
4. Déconnexion → Invalide les tokens
```

### 2. **Où stocker les tokens**
- **Frontend** : `localStorage` ou `sessionStorage`
- **Tests** : Variables d'environnement ou fichiers de configuration
- **Postman** : Variables d'environnement
- **Swagger** : Bouton "Authorize"

## 📤 Envoi de Requêtes avec Token

### **Format Standard (pour toutes les requêtes authentifiées)**

#### **En-têtes HTTP requis**
```http
Authorization: Bearer votre_access_token_ici
Content-Type: application/json
```

### **Exemples Concrets**

#### **1. Requête GET avec Token (JavaScript Fetch)**
```javascript
// Récupérer les informations utilisateur
const token = localStorage.getItem('access_token');

fetch('http://localhost:8000/api/auth/me', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

#### **2. Requête POST avec Token (JavaScript Fetch)**
```javascript
// Créer un nouveau document
const token = localStorage.getItem('access_token');
const documentData = {
  title: "Nouveau document",
  file_path: "/documents/nouveau.pdf",
  file_type: "pdf"
};

fetch('http://localhost:8000/api/documents', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(documentData)
})
.then(response => response.json())
.then(data => console.log('Document créé:', data))
.catch(error => console.error('Error:', error));
```

#### **3. Requête avec Token (Python Requests)**
```python
import requests

token = "votre_access_token"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Requête GET
response = requests.get(
    "http://localhost:8000/api/conversations",
    headers=headers
)
print(response.json())

# Requête POST
data = {"question": "Quel est votre rôle ?"}
response = requests.post(
    "http://localhost:8000/api/chat",
    headers=headers,
    json=data
)
print(response.json())
```

#### **4. Requête avec Token (cURL)**
```bash
# GET request
curl -X GET "http://localhost:8000/api/auth/me" \
     -H "Authorization: Bearer votre_access_token" \
     -H "Content-Type: application/json"

# POST request
curl -X POST "http://localhost:8000/api/documents" \
     -H "Authorization: Bearer votre_access_token" \
     -H "Content-Type: application/json" \
     -d '{"title": "Test", "file_path": "/test.pdf", "file_type": "pdf"}'
```

## 🔄 Réutilisation des Tokens

### **1. Stockage et Réutilisation**
```javascript
// Après connexion réussie
const response = await fetch('/api/auth/login', {
  method: 'POST',
  body: JSON.stringify({username: 'user', password: 'pass'})
});
const {access_token, refresh_token} = await response.json();

// Stockage
localStorage.setItem('access_token', access_token);
localStorage.setItem('refresh_token', refresh_token);

// Réutilisation dans d'autres requêtes
function apiRequest(url, method = 'GET', data = null) {
  const token = localStorage.getItem('access_token');
  const options = {
    method,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  };

  if (data) {
    options.body = JSON.stringify(data);
  }

  return fetch(url, options);
}

// Utilisation
apiRequest('/api/conversations', 'GET')
  .then(r => r.json())
  .then(console.log);
```

### **2. Gestion de l'Expiration**

```javascript
async function makeAuthenticatedRequest(url, method = 'GET', data = null) {
  let token = localStorage.getItem('access_token');

  // Premier essai
  let response = await fetch(url, {
    method,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: data ? JSON.stringify(data) : null
  });

  // Si token expiré (401), rafraîchir et réessayer
  if (response.status === 401) {
    const refreshResponse = await fetch('/api/auth/refresh', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('refresh_token')}`,
        'Content-Type': 'application/json'
      }
    });

    if (refreshResponse.ok) {
      const {access_token: newToken} = await refreshResponse.json();
      localStorage.setItem('access_token', newToken);

      // Réessayer avec le nouveau token
      response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${newToken}`,
          'Content-Type': 'application/json'
        },
        body: data ? JSON.stringify(data) : null
      });
    }
  }

  return response;
}
```

## 🛡️ Bonnes Pratiques de Sécurité

### **1. Ne jamais exposer les tokens**
- ❌ Dans les URLs (`?token=...`)
- ❌ Dans les logs
- ❌ Dans le code source

### **2. Rotation des tokens**
- Utilisez le refresh token pour obtenir de nouveaux access tokens
- Limitez la durée de vie des tokens

### **3. Déconnexion propre**
```javascript
// Déconnexion
async function logout() {
  const token = localStorage.getItem('access_token');

  try {
    await fetch('/api/auth/logout', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
  } finally {
    // Supprimer les tokens même en cas d'erreur
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/login';
  }
}
```

## 📋 Exemples par Route

### **1. Récupération des Conversations (GET)**
```javascript
const token = localStorage.getItem('access_token');

fetch('/api/conversations', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${token}`
  }
})
.then(r => r.json())
.then(conversations => {
  conversations.forEach(conv => {
    console.log(`Conversation: ${conv.title} (${conv.id})`);
  });
});
```

### **2. Poser une Question (POST)**
```javascript
const token = localStorage.getItem('access_token');
const questionData = {
  question: "Quelles sont les missions du ministère?",
  conversation_id: "123e4567-e89b-12d3-a456-426614174000"
};

fetch('/api/chat', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(questionData)
})
.then(r => r.json())
.then(response => {
  console.log('Réponse:', response.text);
  console.log('Sources:', response.sources);
});
```

### **3. Création de Document (POST - Admin)**
```javascript
const token = localStorage.getItem('access_token');
const docData = {
  title: "Rapport Annuel 2024",
  file_path: "/documents/rapport-2024.pdf",
  file_type: "pdf",
  status: "published"
};

fetch('/api/admin/documents', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(docData)
})
.then(r => r.json())
.then(doc => console.log('Document créé:', doc.id));
```

## 🔧 Dépannage

### **Problème : 401 Unauthorized**
1. Vérifiez que le token est valide et non expiré
2. Vérifiez le format : `Bearer token` (avec espace)
3. Obtenez un nouveau token si nécessaire

### **Problème : 403 Forbidden**
1. Vérifiez que votre utilisateur a le bon rôle
2. Pour les routes admin, assurez-vous d'avoir le rôle "admin"
3. Contactez l'administrateur si nécessaire

### **Problème : CORS**
Assurez-vous que votre frontend est dans les origines autorisées (`cors_origins` dans `backend/core/config.py`)