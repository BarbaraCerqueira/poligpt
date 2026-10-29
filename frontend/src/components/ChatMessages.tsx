import React from 'react';
import { useChat } from '../hooks/useChat';
import ChatMessage from './ChatMessage';

const ChatMessages: React.FC = () => {
  const { currentChat } = useChat();
  const messages = currentChat?.messages || [];

  if (messages.length === 0) {
    return null;
  }

  return (
    <div className="space-y-6">
      {messages.map((message, index) => (
        <ChatMessage key={index} message={message} />
      ))}
    </div>
  );
};

export default ChatMessages;
