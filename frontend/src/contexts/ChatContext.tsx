import React, { createContext, useState, useEffect, ReactNode, useRef } from 'react';
import { AccessDeniedError, Source, streamChatMessage } from '../services/api';

// Define types for our context
export interface Message {
  role: 'user' | 'assistant';
  content: string;
  status?: string; // what the assistant is doing before the answer starts (e.g. 'searching')
  sources?: Source[]; // documents cited in the answer
  error?: boolean; // the answer failed and shows an error message instead
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
  sendMessage: (content: string) => Promise<void>;
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
          : 'Nova conversa',
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
    // Only one answer at a time, even if the user switched to another chat
    if (isLoading) return;
    const chatId = currentChatId;

    // Prepare the chat history in the format expected by the API, leaving out failed answers and their questions
    const chatHistory = currentChat?.messages.filter((msg, i, all) => !msg.error && !all[i + 1]?.error).map(msg => ({
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
        ? 'Seu código de acesso não é mais válido. Informe um novo código e envie a pergunta outra vez.'
        : 'Não foi possível gerar a resposta agora. Tente novamente em instantes.';
      updateLastMessage(chatId, msg => ({
        ...msg,
        status: undefined,
        error: true,
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
    sendMessage,
    deleteChat,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
};