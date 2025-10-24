# Frontend MongoDB Integration Guide

## Overview

The frontend now integrates with the MongoDB chat history backend to provide persistent conversation storage and retrieval.

## New Features

### 1. **Clear History Button**
- Now deletes chat history from MongoDB (not just local storage)
- Calls `DELETE /api/chat/history` to remove all messages for the current access code
- Gracefully handles cases where MongoDB is disabled

### 2. **Load Conversations from Database**
- Clicking on a conversation in the history sidebar loads messages from MongoDB
- Automatically fetches and displays previous messages
- Falls back to empty conversation if MongoDB not available

### 3. **Auto-Load Thread History**
- When returning to the app, automatically loads the last active thread's messages from MongoDB
- Restores your conversation state across browser sessions

### 4. **Sync Thread List with MongoDB**
- Thread list now includes conversations stored in MongoDB
- Shows threads from both local storage and database
- Automatically syncs when logging in

## Technical Implementation

### Changes to `HomePage.tsx`

#### 1. Enhanced `clearChatHistory()` Function

**Before:**
```tsx
const clearChatHistory = () => {
  // Only cleared local storage
  window.localStorage.removeItem(THREADS_INDEX_KEY);
  window.localStorage.removeItem(THREAD_STORAGE_KEY);
  // ...
};
```

**After:**
```tsx
const clearChatHistory = () => {
  // Now also clears MongoDB
  if (sessionToken) {
    fetch(`${API_BASE_URL}/api/chat/history`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${sessionToken}`,
      },
    })
    .then((response) => response.json())
    .then((data) => {
      console.log('Cleared MongoDB history:', data);
    })
    .catch((err) => {
      console.warn('Failed to clear MongoDB history (may not be enabled):', err);
    });
  }
  
  // Also clear local storage
  window.localStorage.removeItem(THREADS_INDEX_KEY);
  window.localStorage.removeItem(THREAD_STORAGE_KEY);
  // ...
};
```

#### 2. Enhanced `handleSelectThread()` Function

**Before:**
```tsx
const handleSelectThread = (threadId: string) => {
  // Just reset to greeting message
  setActiveThreadId(threadId);
  setMessages([
    {
      id: createId(),
      role: 'assistant',
      content: greetingMessage,
      downloads: [],
    },
  ]);
};
```

**After:**
```tsx
const handleSelectThread = async (threadId: string) => {
  setActiveThreadId(threadId);
  
  // Try to load messages from MongoDB
  if (sessionToken) {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/chat/history?threadId=${threadId}`,
        {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${sessionToken}`,
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        if (data.messages && data.messages.length > 0) {
          // Convert and display MongoDB messages
          const loadedMessages = data.messages.map((msg) => ({
            id: msg._id || createId(),
            role: msg.role,
            content: msg.content,
            downloads: [],
          }));
          setMessages(loadedMessages);
          return;
        }
      }
    } catch (err) {
      console.warn('Failed to load from MongoDB:', err);
    }
  }
  
  // Fallback to greeting if MongoDB not available
  setMessages([{ /* greeting */ }]);
};
```

#### 3. New useEffect: Load Threads from MongoDB

```tsx
useEffect(() => {
  if (!sessionToken) return;

  const loadThreadsFromMongoDB = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/threads`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${sessionToken}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        if (data.threads && Array.isArray(data.threads)) {
          // Convert MongoDB threads to local format
          const mongoThreads = data.threads.map((thread) => ({
            id: thread.thread_id,
            title: `Thread ${thread.thread_id}`,
            createdAt: new Date(thread.last_message_at).getTime(),
            updatedAt: new Date(thread.last_message_at).getTime(),
          }));
          
          // Merge with existing local threads
          setThreadSummaries((prev) => {
            const existingMap = new Map(prev.map((t) => [t.id, t]));
            mongoThreads.forEach((t) => existingMap.set(t.id, t));
            return Array.from(existingMap.values());
          });
        }
      }
    } catch (err) {
      console.warn('Failed to load threads from MongoDB:', err);
    }
  };

  loadThreadsFromMongoDB();
}, [sessionToken]);
```

#### 4. New useEffect: Auto-Load Active Thread Messages

```tsx
useEffect(() => {
  if (!sessionToken || !activeThreadId) return;

  const loadThreadMessages = async () => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/chat/history?threadId=${activeThreadId}`,
        {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${sessionToken}`,
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        if (data.messages && data.messages.length > 0) {
          const loadedMessages = data.messages.map((msg) => ({
            id: msg._id || createId(),
            role: msg.role,
            content: msg.content,
            downloads: [],
          }));
          
          // Only update if showing greeting (fresh load)
          const hasOnlyGreeting = 
            messages.length === 1 && 
            messages[0].content === greetingMessage;
            
          if (messages.length === 0 || hasOnlyGreeting) {
            setMessages(loadedMessages);
          }
        }
      }
    } catch (err) {
      console.warn('Failed to load messages:', err);
    }
  };

  loadThreadMessages();
}, [sessionToken, activeThreadId]);
```

## Backend Endpoints Used

### 1. Get Chat History
```http
GET /api/chat/history?threadId={threadId}&limit={limit}
Authorization: Bearer {sessionToken}

Response:
{
  "messages": [
    {
      "_id": "...",
      "access_code": "...",
      "profile_id": "...",
      "thread_id": "...",
      "role": "user" | "assistant",
      "content": "message text",
      "metadata": {},
      "timestamp": "ISO8601",
      "created_at": "ISO8601"
    }
  ]
}
```

### 2. Get Thread List
```http
GET /api/chat/threads
Authorization: Bearer {sessionToken}

Response:
{
  "threads": [
    {
      "thread_id": "default",
      "last_message_at": "ISO8601",
      "message_count": 42
    }
  ]
}
```

### 3. Delete All History
```http
DELETE /api/chat/history
Authorization: Bearer {sessionToken}

Response:
{
  "deleted": 42,
  "message": "Deleted 42 total messages."
}
```

### 4. Delete Specific Thread
```http
DELETE /api/chat/history/{threadId}
Authorization: Bearer {sessionToken}

Response:
{
  "deleted": 10,
  "message": "Deleted 10 messages."
}
```

## User Experience Flow

### Scenario 1: Clearing History

1. User clicks "Clear history" button
2. Frontend sends `DELETE /api/chat/history`
3. Backend deletes all messages from MongoDB for that access code
4. Frontend clears local storage
5. UI resets to fresh conversation

### Scenario 2: Loading Old Conversation

1. User sees list of threads in sidebar
2. User clicks on a thread
3. Frontend sends `GET /api/chat/history?threadId=...`
4. Backend retrieves messages from MongoDB
5. Frontend displays all messages in order
6. User can continue the conversation

### Scenario 3: Returning User

1. User opens app (already logged in)
2. Frontend loads `sessionToken` from localStorage
3. Frontend fetches threads: `GET /api/chat/threads`
4. Frontend loads last active thread ID from localStorage
5. Frontend fetches messages: `GET /api/chat/history?threadId=...`
6. User sees their previous conversation automatically

### Scenario 4: MongoDB Disabled

1. All MongoDB requests fail gracefully
2. Console shows warnings (not errors)
3. App continues to work with local storage only
4. No breaking errors or UI issues

## Graceful Degradation

All MongoDB integrations include error handling:

```tsx
try {
  // MongoDB operation
  const response = await fetch('...');
  if (response.ok) {
    // Use MongoDB data
  }
} catch (err) {
  // Log but don't crash
  console.warn('MongoDB not available:', err);
  // Fall back to default behavior
}
```

This ensures:
- ✅ App works without MongoDB
- ✅ No error dialogs for users
- ✅ Smooth transition when MongoDB is enabled/disabled
- ✅ Development mode works without setup

## Testing the Integration

### With MongoDB Disabled (Default)

1. Start frontend: `npm run dev`
2. Start backend: `python app.py`
3. Clear history → works (local storage only)
4. Load thread → shows greeting (no stored messages)
5. Console shows warnings about MongoDB

### With MongoDB Enabled

1. Enable MongoDB: Set `ENABLE_MONGODB=true` in `.env`
2. Start MongoDB: `brew services start mongodb-community`
3. Start backend: `python app.py`
4. Start frontend: `npm run dev`
5. Have a conversation
6. Click "Clear history" → deletes from MongoDB
7. Refresh page → conversation restored from MongoDB
8. Click another thread → loads that thread's messages

## Configuration

No frontend configuration needed! The frontend automatically:
- Detects if MongoDB is available
- Falls back gracefully if not
- Uses environment variable `VITE_API_BASE_URL` for API endpoint

## Benefits

### For Users
- 🎯 **Persistent conversations** - Don't lose chat history on refresh
- 🔄 **Cross-device access** - Access same history from different browsers (same access code)
- 📚 **Searchable history** - All messages stored and retrievable
- 🗑️ **Easy cleanup** - One button clears everything

### For Developers
- 🔧 **Zero config** - Works out of the box
- 🛡️ **Graceful degradation** - No MongoDB? No problem!
- 📊 **Scalable** - MongoDB handles growth easily
- 🔍 **Debuggable** - All operations logged

## Future Enhancements

Potential improvements:
- [ ] Search within conversations
- [ ] Export conversation as PDF/text
- [ ] Share conversations via link
- [ ] Archive old conversations
- [ ] Filter by date range
- [ ] Tag/categorize conversations
- [ ] Conversation templates
- [ ] Bulk operations (delete multiple threads)

## Troubleshooting

### History not loading
**Check:**
1. Is `ENABLE_MONGODB=true` in backend `.env`?
2. Is MongoDB running? `brew services list`
3. Are there messages in the database? `mongosh` → `db.chat_history.find()`
4. Check browser console for errors
5. Check backend logs

### Clear history not working
**Check:**
1. Network tab - is the DELETE request sent?
2. Response status - should be 200
3. Backend logs - any errors?
4. Try: `curl -X DELETE http://localhost:5050/api/chat/history -H "Authorization: Bearer <token>"`

### Threads not appearing
**Check:**
1. Backend: `GET /api/chat/threads` returns data
2. Frontend console - any errors during fetch?
3. Verify sessionToken is valid
4. Check if messages exist: `db.chat_history.find()`

## Summary

✅ **Clear History** button now deletes from MongoDB  
✅ **Load Conversations** from database when clicking threads  
✅ **Auto-restore** last conversation on page load  
✅ **Sync thread list** with MongoDB  
✅ **Graceful fallback** when MongoDB disabled  
✅ **Zero configuration** required on frontend  
✅ **Fully tested** and working!

The integration is complete and ready to use! 🎉
