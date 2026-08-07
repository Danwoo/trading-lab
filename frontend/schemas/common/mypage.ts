export interface UserInfo {
  email: string;
  name: string;
  dept: string;
}

export interface UpdateUserIn {
  email: string;
  password?: string;
  name: string;
  dept: string;
}

export interface MyInfoOut {
  result: boolean;
  resultList: UserInfo[];
}

export interface UpdateMyInfoOut {
  result: boolean;
  name?: string;
}
