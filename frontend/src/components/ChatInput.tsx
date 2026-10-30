import React, { useState, FormEvent, useRef, useEffect } from 'react';
import { Send } from 'lucide-react';
import { useChat } from '../hooks/useChat';

const ChatInput: React.FC = () => {
  const [message, setMessage] = useState('');
  const { sendMessage, isLoading } = useChat();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    // Focus the textarea when the component mounts
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, []);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    }
  }, [message]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (message.trim() && !isLoading) {
      // Clear the input right away: the answer is streamed and may take a few seconds
      setMessage('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
      await sendMessage(message);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex items-start">
      <form 
        onSubmit={handleSubmit} 
        className="relative flex items-end flex-1 bg-white dark:bg-gray-800 rounded-2xl shadow-lg"
      >
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Pergunte sobre a Poli..."
          rows={1}
          className="flex-1 py-4 px-4 pr-12 bg-transparent border border-gray-300 dark:border-gray-600 rounded-2xl focus:outline-none focus:ring-2 focus:ring-navy-500 dark:focus:ring-navy-400 focus:border-transparent text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 resize-none min-h-[56px] max-h-[200px] [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]"
        />
        <button
          type="submit"
          disabled={!message.trim() || isLoading}
          className="absolute right-2 bottom-2 p-2 rounded-xl text-navy-700 dark:text-navy-300 hover:bg-navy-100 dark:hover:bg-navy-600/40 disabled:opacity-50 disabled:hover:bg-transparent transition-colors"
        >
          <Send size={24} />
        </button>
      </form>
    </div>
  );
};

export default ChatInput;