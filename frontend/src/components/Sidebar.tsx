import React, { useState } from 'react';
import { MessageSquare, Info, Link2, PlusSquare, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import Logo from './Logo';
import { useChat } from '../hooks/useChat';

interface SidebarProps {
  onCloseMobile: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ onCloseMobile }) => {
  const { chats, currentChatId, newChat, switchChat, deleteChat } = useChat();
  const [isAboutExpanded, setIsAboutExpanded] = useState(false);
  
  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Logo */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <Logo className="mx-auto w-40" />
      </div>
      
      {/* New Chat Button */}
      <div className="px-4 py-4">
        <button
          onClick={() => { newChat(); onCloseMobile(); }}
          className="flex items-center w-full px-4 py-3 bg-navy-700 hover:bg-navy-800 dark:hover:bg-navy-600 text-white rounded-lg transition-colors"
        >
          <PlusSquare className="mr-3 h-5 w-5" />
          <span className="font-medium">Nova conversa</span>
        </button>
      </div>
      
      {/* Chat List */}
      <div className="flex-1 flex flex-col min-h-0">

        <div className="flex-1 overflow-y-auto space-y-1 scrollbar scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-700 
          scrollbar-track-transparent hover:scrollbar-thumb-gray-400 
          dark:hover:scrollbar-thumb-gray-600 scrollbar-thumb-rounded-full px-2 pb-2 pt-2">
          {chats.map(chat => (
            <div 
              key={chat.id} 
              className="flex items-center relative group"
            >
              <button
                onClick={() => { switchChat(chat.id); onCloseMobile(); }}
                className={`flex items-center w-full px-4 py-2 rounded-lg transition-colors ${
                  chat.id === currentChatId 
                    ? 'bg-navy-600/15 dark:bg-navy-600/40 text-navy-800 dark:text-navy-200' 
                    : 'hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
                }`}
              >
                <MessageSquare className="mr-3 h-4 w-4 flex-shrink-0" />
                <span className={`font-medium truncate ${chat.id === currentChatId ? 'mr-7' : 'mr-7 md:mr-0 md:group-hover:mr-7'}`}>
                  {chat.title}
                </span>
              </button>
              {/* Touch screens have no hover, so below the md breakpoint the delete button is always visible */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  deleteChat(chat.id);
                }}
                className={`absolute right-2 p-1.5 text-gray-500 hover:text-red-500 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-full transition-all ${
                  chat.id === currentChatId
                    ? 'opacity-100'
                    : 'opacity-100 md:opacity-0 md:group-hover:opacity-100 focus:opacity-100'
                }`}
                title="Excluir conversa"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      </div>
      
      {/* Information */}
      <div className="border-t border-gray-200 dark:border-gray-700 mt-auto overflow-hidden">
        <button
          onClick={() => setIsAboutExpanded(!isAboutExpanded)}
          className="flex items-center justify-between w-full px-4 py-3 text-left transition-colors hover:bg-gray-200 dark:hover:bg-gray-700"
        >
          <div className="flex items-center">
            <div className="flex justify-center items-center w-8 h-8 rounded-full bg-navy-100 dark:bg-navy-600/30 mr-3">
              <Info className="h-4 w-4 text-navy-700 dark:text-navy-300" />
            </div>
            <span className="font-medium text-gray-900 dark:text-gray-100">Sobre o PoliGPT</span>
          </div>
          {isAboutExpanded ? (
            <ChevronUp className="h-5 w-5 text-gray-500" />
          ) : (
            <ChevronDown className="h-5 w-5 text-gray-500" />
          )}
        </button>
        
        <div 
          className={`px-4 overflow-hidden transition-all duration-300 ease-in-out ${
            isAboutExpanded ? "max-h-96 opacity-100 pb-4" : "max-h-0 opacity-0 pb-0"
          }`}
        >
          <div className="p-3 rounded-lg bg-gradient-to-br from-navy-50 to-navy-100 dark:from-gray-800 dark:to-gray-700/50 border border-navy-100 dark:border-gray-700 text-sm">
            <p className="text-gray-600 dark:text-gray-300 mb-2 leading-relaxed">
              O PoliGPT responde dúvidas sobre a Escola Politécnica da UFRJ com base no conteúdo público
              do site da Poli e indica as fontes de cada resposta.
            </p>
            <p className="text-gray-600 dark:text-gray-300 mb-3 leading-relaxed">
              É um protótipo desenvolvido como Projeto de Graduação e pode errar. Na dúvida, confira as
              fontes ou procure a secretaria responsável.
            </p>

            <a 
              href="https://www.poli.ufrj.br/" 
              target="_blank" 
              rel="noopener noreferrer"
              className="flex items-center justify-center py-2 px-3 text-sm bg-navy-700 hover:bg-navy-800 dark:hover:bg-navy-600 text-white rounded-md transition-colors"
            >
              <Link2 className="mr-2 h-4 w-4" />
              Acessar o site da Poli
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;