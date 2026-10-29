import React from 'react';
import { Message } from '../contexts/ChatContext';
import { Source } from '../services/api';
import { User } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ChatMessageProps {
  message: Message;
}

// Turns citations like [1] into links to the cited document, when it has a URL. Citations are renumbered by
// the source's position (1, 2, 3...), since only the cited documents are returned and their ids can skip numbers
const linkCitations = (content: string, sources: Source[] = []): string =>
  content.replace(/\[(\d+)\]/g, (citation, id) => {
    const index = sources.findIndex(s => s.id === Number(id));
    if (index === -1) return citation;
    const number = `[${index + 1}]`;
    return sources[index].url ? `[${number}](<${sources[index].url}>)` : number;
  });

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const name = message.role === 'user' ? 'Você' : 'PoliGPT';
  const isWaiting = message.role === 'assistant' && !message.content;

  return (
    <div 
      className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} animate-fadeIn`}
    >
      <div 
        className={`flex max-w-full ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'} items-start`}
      >
        <div className="flex flex-col items-center mx-2 sm:mx-3">
          {/* The assistant uses the PoliGPT icon (public/poligpt_icon.svg), the same one shown in the browser tab */}
          {message.role === 'user' ? (
            <div className="h-10 w-10 flex items-center justify-center rounded-full bg-gray-300 dark:bg-gray-600 text-gray-600 dark:text-gray-200 shadow-sm">
              <User className="h-6 w-6" />
            </div>
          ) : (
            <img src="/poligpt_icon.svg" alt="" className="h-10 w-10" />
          )}
          <span className="text-xs text-gray-500 dark:text-gray-400 mt-1">{name}</span>
        </div>
        <div 
          className={`min-w-0 rounded-2xl px-4 sm:px-5 py-3 ${
            message.role === 'user' 
              ? 'bg-blue-600 dark:bg-blue-700 text-white rounded-tr-none shadow-md' 
              : 'bg-white/80 dark:bg-gray-700 text-gray-700 dark:text-gray-100 rounded-tl-none shadow-md'
          }`}
        >
          {isWaiting ? (
            <div className="flex items-center gap-2 py-1 text-sm text-gray-500 dark:text-gray-300">
              <div className="animate-pulse flex space-x-1">
                <div className="h-2 w-2 bg-blue-600 rounded-full"></div>
                <div className="h-2 w-2 bg-blue-600 rounded-full"></div>
                <div className="h-2 w-2 bg-blue-600 rounded-full"></div>
              </div>
              {message.status === 'searching' && <span>Buscando nos documentos da Poli...</span>}
            </div>
          ) : message.role === 'assistant' ? (
            <>
            <div className="prose prose-sm sm:prose-base dark:prose-invert max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: (props) => (
                  <a className="text-blue-600 underline dark:text-blue-400" target="_blank" rel="noopener noreferrer" {...props} />
                ),
                table: (props) => (
                  <div className="not-prose my-3 overflow-x-auto">
                    <table className="min-w-full border-collapse text-sm" {...props} />
                  </div>
                ),
                th: (props) => (
                  <th className="border border-gray-300 dark:border-gray-500 bg-gray-100 dark:bg-gray-600 px-3 py-2 text-left font-semibold" {...props} />
                ),
                td: (props) => (
                  <td className="border border-gray-300 dark:border-gray-500 px-3 py-2 align-top" {...props} />
                )
              }}
            >
              {linkCitations(message.content, message.sources)}
            </ReactMarkdown>
            </div>
            {message.sources && message.sources.length > 0 && (
              <div className="mt-3 pt-2 border-t border-gray-300 dark:border-gray-600 text-sm">
                <p className="font-semibold mb-1">Fontes</p>
                <ul className="space-y-1">
                  {message.sources.map((source, index) => (
                    <li key={source.id}>
                      [{index + 1}]{' '}
                      {source.url ? (
                        <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline dark:text-blue-400">
                          {source.title}
                        </a>
                      ) : source.title}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            </>
          ) : (
            <p className="whitespace-pre-wrap">{message.content}</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;