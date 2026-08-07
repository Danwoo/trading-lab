export interface CommonEntity {
  rn?: number;
  reg_dt?: string;
  reg_id?: string;
  mod_dt?: string;
  mod_id?: string;
}

export interface CreateOut {
  message?: string;
  data?: any;
}

export interface UpdateOut {
  message?: string;
}

export interface DeleteOut {
  message?: string;
}

export interface MessageOut {
  message?: string;
  level?: "success" | "warning" | "info" | "error";
}
