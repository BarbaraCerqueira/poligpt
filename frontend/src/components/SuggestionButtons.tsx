import React from 'react';
import { useChat } from '../hooks/useChat';
import { BookOpen, Briefcase, Globe } from 'lucide-react';

interface SuggestionButtonsProps {
  suggestions: string[];
}

const SuggestionButtons: React.FC<SuggestionButtonsProps> = ({ suggestions }) => {
  const { sendMessage, currentChat, isLoading } = useChat();
  const messages = currentChat?.messages || [];

  // Don't show suggestions if chat has already started
  if (messages.length > 0) {
    return null;
  }

  const icons = [
    <BookOpen className="w-6 h-6" />,
    <Briefcase className="w-6 h-6" />,
    <Globe className="w-6 h-6" />
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 sm:gap-4">
      {suggestions.map((suggestion, index) => (
        <button
          key={index}
          onClick={() => sendMessage(suggestion)}
          disabled={isLoading}
          className="flex items-center gap-4 px-6 py-4 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-xl text-left transition-all duration-200 group disabled:opacity-50 disabled:pointer-events-none"
        >
          <div className="text-gray-500 dark:text-gray-400 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
            {icons[index]}
          </div>
          <span className="text-sm text-gray-700 dark:text-gray-300">
            {suggestion}
          </span>
        </button>
      ))}
    </div>
  );
};

export default SuggestionButtons;
