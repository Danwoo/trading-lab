// utils/common/locale/en/apierrors.ts
// API 에러 클라이언트 폴백 메시지 (English). 로직은 errors/apierrors.ts, ko 는 ../ko/apierrors.ts.

import type { EmailFailureCode } from "@/utils/common/errors/emailFailure";
import type { StreamFailureCode } from "@/utils/common/errors/streamFailure";

export const STATUS_MESSAGES: Record<number, string> = {
  400: "Bad request.",
  401: "Your session has ended. Please sign in again.",
  403: "You do not have permission to access this.",
  404: "The requested resource was not found.",
  405: "Method not allowed.",
  408: "The request timed out.",
  409: "A conflict occurred with existing data.",
  410: "This data is no longer available.",
  413: "The request data is too large.",
  415: "Unsupported format.",
  416: "The requested range is invalid.",
  422: "Please check your input.",
  429: "Too many requests. Please try again later.",
  500: "The server hit an error. Please try again shortly.",
  502: "Invalid response from an external service. Please try again shortly.",
  503: "The service is not responding right now. Please try again shortly.",
  504: "The external service response timed out. Please try again shortly.",
};

export const FALLBACK = {
  processing: "An error occurred while processing the request.",
  network: "Please check your network connection",
  unknown: "An unknown error occurred",
};

// Mail delivery failure reasons — key = EmailFailureCode from errors/emailFailure.ts.
// The server sends only the code; the raw SMTP text stays in the log (#342).
export const EMAIL_FAILURE_MESSAGES: Record<EmailFailureCode, string> = {
  "email.mailbox_unknown": "That email address does not exist.\nPlease check the address.",
  "email.mailbox_rejected": "That email address refused the message.\nPlease try another address.",
  "email.smtp_unreachable": "The mail server could not be reached.\nTry again shortly or contact an administrator.",
  "email.smtp_auth_failed": "The mail server rejected our sign-in.\nPlease contact an administrator.",
  "email.send_failed": "The email could not be sent.\nCheck the address or try again shortly.",
};

// Streaming-chat failure reasons — key = StreamFailureCode from errors/streamFailure.ts.
// These say what to do: retrying does not help for any of them (#423).
export const STREAM_FAILURE_MESSAGES: Record<StreamFailureCode, string> = {
  "botAgent.service_unreachable":
    "The bot conversation service (:8011) is not running.\nRetrying will not connect — start the service, then send again.",
  "botAgent.invalid_api_key":
    "The bot conversation API key was rejected.\nA key that is set is not necessarily valid — replace the key, then send again.",
  "botAgent.turn_failed":
    "The conversation did not finish.\nWhat arrived above is kept. If this keeps happening, check the server log.",
  "research.service_unreachable":
    "The research service (:8003) is not running.\nRetrying will not connect — start the service, then ask again.",
};

// Prisma error translations — key = type emitted by lib/prisma/error.ts (real code P#### / prisma_*)
// Code meanings follow the official Prisma error-reference. DB-only — no client-side pre-validation.
export const PRISMA_ERROR_MAP = new Map<string, string>([
  // Connection / engine (P1xxx)
  ["P1000", "Database authentication failed"],
  ["P1001", "Cannot reach the database server"],
  ["P1002", "The database server timed out"],
  ["P1003", "The database does not exist"],
  ["P1008", "The database operation timed out"],
  ["P1009", "The database already exists"],
  ["P1010", "Access to the database was denied"],
  ["P1011", "A TLS connection error occurred"],
  ["P1012", "Database schema validation failed"],
  ["P1013", "The database connection string is invalid"],
  ["P1014", "The underlying table or view does not exist"],
  ["P1015", "The database version does not support a used feature"],
  ["P1016", "The query has an incorrect number of parameters"],
  ["P1017", "The database connection was closed"],
  // Query (P2xxx)
  ["P2000", "The entered value is too long"],
  ["P2001", "No record matches the given condition"],
  ["P2002", "This value is already in use"],
  ["P2003", "The referenced data is invalid"],
  ["P2004", "A data constraint was violated"],
  ["P2005", "A stored value is invalid for its field type"],
  ["P2006", "The provided value is invalid"],
  ["P2007", "Data validation failed"],
  ["P2008", "Failed to parse the query"],
  ["P2009", "Failed to validate the query"],
  ["P2010", "The query failed to execute"],
  ["P2011", "A required value is missing"],
  ["P2012", "A required value is missing"],
  ["P2013", "A required argument is missing"],
  ["P2014", "Cannot proceed because related data exists"],
  ["P2015", "A related record could not be found"],
  ["P2016", "A query interpretation error occurred"],
  ["P2017", "The related records are not connected"],
  ["P2018", "The required connected records were not found"],
  ["P2019", "There is an input error"],
  ["P2020", "The value is out of range"],
  ["P2021", "The target table does not exist"],
  ["P2022", "The target column does not exist"],
  ["P2023", "Inconsistent column data was detected"],
  ["P2024", "The database connection pool timed out"],
  ["P2025", "The requested data was not found"],
  ["P2026", "The database does not support a used feature"],
  ["P2027", "Multiple errors occurred during query execution"],
  ["P2028", "A transaction error occurred"],
  ["P2029", "The query parameter limit was exceeded"],
  ["P2030", "No fulltext index was found for the search"],
  ["P2031", "MongoDB must be run as a replica set"],
  ["P2033", "A number is out of the supported range"],
  ["P2034", "The operation failed due to a write conflict. Please try again"],
  ["P2035", "A database assertion was violated"],
  ["P2036", "An external connector error occurred"],
  ["P2037", "Too many database connections are open"],
  // Errors without a code
  ["prisma_validation_error", "Please check the request data"],
  ["prisma_initialization_error", "Failed to connect to the database"],
  ["prisma_rust_panic_error", "A database engine error occurred"],
  ["prisma_unknown_error", "An error occurred while processing data"],
  ["prisma_general_error", "An error occurred"],
]);
