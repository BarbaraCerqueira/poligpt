import React, { createContext, useState, useEffect, ReactNode, useRef } from 'react';
import { AccessDeniedError, Source, streamChatMessage } from '../services/api';

// Define types for our context
export interface Message {
  role: 'user' | 'assistant';
  content: string;
  status?: string; // what the assistant is doing before the answer starts (e.g. 'searching')
  sources?: Source[]; // documents cited in the answer
}

export interface Chat {
  id: string; // uuid
  title: string;
  messages: Message[];
}

interface ChatContextType {
  chats: Chat[];
  currentChatId: string;
  isLoading: boolean;
  switchChat: (id: string) => void;
  newChat: () => void;
  appendMessage: (message: Message) => void;
  sendMessage: (content: string) => Promise<void>;
  clearCurrentChat: () => void;
  currentChat: Chat | undefined;
  deleteChat: (id: string) => void;
}

// Create the context with a default value
export const ChatContext = createContext<ChatContextType | undefined>(undefined);

interface ChatProviderProps {
  children: ReactNode;
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
  const [chats, setChats] = useState<Chat[]>([]);
  const [currentChatId, setCurrentChatId] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const initialized = useRef(false);
  const pendingChatId = useRef<string | null>(null);

  // Get the current active chat
  const currentChat = chats.find(chat => chat.id === currentChatId);

  // For compatibility with existing components
  const messages = currentChat?.messages || [];
  
  // Initialize with a first chat
  useEffect(() => {
    if (!initialized.current && chats.length === 0) {
      const newChatId = crypto.randomUUID();
      pendingChatId.current = newChatId;
      setCurrentChatId(newChatId);
      initialized.current = true;
    }
  }, [chats.length]);

  const newChat = () => {
    const newChatId = crypto.randomUUID();
    pendingChatId.current = newChatId;
    setCurrentChatId(newChatId);
  };

  const switchChat = (id: string) => {
    const chatExists = chats.some(chat => chat.id === id);
    if (chatExists) {
      pendingChatId.current = null;
      setCurrentChatId(id);
    }
  };

  const deleteChat = (id: string) => {
    setChats(prevChats => prevChats.filter(chat => chat.id !== id));
    
    // If we're deleting the current chat, switch to another one or create a new one
    if (id === currentChatId) {
      if (chats.length > 1) {
        // Find the next available chat to switch to
        const nextChat = chats.find(chat => chat.id !== id);
        if (nextChat) {
          setCurrentChatId(nextChat.id);
        }
      } else {
        // If this was the last chat, create a new one
        newChat();
      }
    }
  };

  const appendMessage = (message: Message) => {
    // Se é um chat pendente, cria um novo chat
    if (pendingChatId.current === currentChatId) {
      const newChat: Chat = {
        id: currentChatId,
        title: message.role === 'user' 
          ? message.content.slice(0, 20) + (message.content.length > 20 ? '...' : '')
          : 'Nova Conversa',
        messages: [message]
      };
      setChats(prevChats => [newChat, ...prevChats]);
      pendingChatId.current = null;
    } else {
      // Atualiza um chat existente
      setChats(prevChats => 
        prevChats.map(chat => 
          chat.id === currentChatId 
            ? { 
                ...chat, 
                messages: [...chat.messages, message],
                title: chat.messages.length === 0 && message.role === 'user' 
                  ? message.content.slice(0, 20) + (message.content.length > 20 ? '...' : '') 
                  : chat.title
              } 
            : chat
        )
      );
    }
  };

  const clearCurrentChat = () => {
    if (pendingChatId.current === currentChatId) {
      // Se for um chat pendente, apenas volta para o último chat existente
      const lastChat = chats[0];
      if (lastChat) {
        setCurrentChatId(lastChat.id);
      }
      pendingChatId.current = null;
    } else {
      // Limpa o chat existente
      setChats(prevChats => 
        prevChats.map(chat => 
          chat.id === currentChatId 
            ? { ...chat, messages: [] } 
            : chat
        )
      );
    }
  };

  // Updates the last message of a chat (the assistant answer being streamed)
  const updateLastMessage = (chatId: string, update: (message: Message) => Message) => {
    setChats(prevChats =>
      prevChats.map(chat =>
        chat.id === chatId
          ? { ...chat, messages: [...chat.messages.slice(0, -1), update(chat.messages[chat.messages.length - 1])] }
          : chat
      )
    );
  };

  const sendMessage = async (content: string) => {
    const chatId = currentChatId;

    // Prepare the chat history in the format expected by the API
    const chatHistory = currentChat?.messages.map(msg => ({
      role: msg.role,
      content: msg.content
    })) || [];

    // Add the user message and an empty assistant message, filled as the answer arrives
    appendMessage({ role: 'user', content });
    appendMessage({ role: 'assistant', content: '' });
    setIsLoading(true);

    try {
      await streamChatMessage({ query: content, chat_history: chatHistory }, {
        // A new search means any text received so far was not the final answer
        onStatus: (status) => updateLastMessage(chatId, msg => ({ ...msg, status, content: '' })),
        onToken: (token) => updateLastMessage(chatId, msg => ({ ...msg, status: undefined, content: msg.content + token })),
        onSources: (sources) => updateLastMessage(chatId, msg => ({ ...msg, sources })),
      });
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = error instanceof AccessDeniedError
        ? 'Seu código de acesso não é mais válido. Informe um novo código e tente novamente.'
        : 'Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente.';
      updateLastMessage(chatId, msg => ({
        ...msg,
        status: undefined,
        content: msg.content ? `${msg.content}\n\n*${errorMessage}*` : errorMessage
      }));
    } finally {
      setIsLoading(false);
    }
  };

  const value = {
    chats,
    currentChatId,
    currentChat,
    isLoading,
    switchChat,
    newChat,
    appendMessage,
    sendMessage,
    clearCurrentChat,
    deleteChat,
    // For compatibility with existing components
    messages
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
};