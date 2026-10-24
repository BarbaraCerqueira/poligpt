import React, { useRef, useEffect, useMemo } from 'react';
import { useChat } from '../hooks/useChat';
import ChatMessage from './ChatMessage';

const ChatMessages: React.FC = () => {
  const { currentChat } = useChat();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messages = useMemo(() => currentChat?.messages || [], [currentChat?.messages]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return null;
  }

  return (
    <div className="w-full h-full">
      <div className="max-w-5xl mx-auto h-full px-8">
        <div className="space-y-6">
          {messages.map((message, index) => (
            <ChatMessage key={index} message={message} />
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>
    </div>
  );
};

export default ChatMessages;