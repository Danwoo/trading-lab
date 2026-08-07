"use client";

import { useFormState } from "@/hooks/shared/useFormState";
import { Button, TextBox, SelectBox, NumberBox, TextArea, TabPanel, TabContent } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { Portfolio } from "@/schemas/portfolio/portfolio";
import PortfolioHoldingGrid from "./PortfolioHoldingGrid";

interface Props {
  isNew: boolean;
  initialData: Partial<Portfolio>;
  onSubmit: (data: Portfolio) => Promise<boolean>;
  onCancel?: () => void;
  codeList?: any;
}

export default function PortfolioDetailForm({ initialData, isNew, codeList, onSubmit, onCancel }: Props) {
  const { formData, handleFieldChange, getFieldProps, handleSubmit } = useFormState<Portfolio>(initialData);

  const canAccessSubTabs = !isNew && !!formData.portfolio_id?.trim();
  const tabs = [
    { id: "basic", text: "포트폴리오", icon: "edit" },
    { id: "holdings", text: "보유종목", icon: "hierarchy", disabled: !canAccessSubTabs },
  ];

  return (
    <div className="h-full">
      <TabPanel items={tabs} defaultTab="basic">
        <TabContent tabId="basic">
          <div className="h-full flex flex-col">
            <div className="flex-shrink-0 mb-2">
              <div className="flex gap-2 justify-end">
                <Button text="저장" onClick={() => handleSubmit(onSubmit)} />
                {onCancel && !isNew && <Button text="취소" onClick={onCancel} stylingMode="outlined" type="normal" />}
              </div>
            </div>

            <div className="flex-1 overflow-auto">
              <TableGroup title="포트폴리오 정보">
                <TableRow>
                  <TableCell label="포트폴리오ID" required>
                    <TextBox
                      fieldName="portfolio_id"
                      value={formData.portfolio_id}
                      readOnly={!isNew}
                      onValueChanged={(_field, value) =>
                        handleFieldChange(
                          "portfolio_id",
                          String(value ?? "")
                            .replace(/\s/g, "")
                            .toLowerCase(),
                        )
                      }
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                  <TableCell label="포트폴리오명" required>
                    <TextBox
                      fieldName="portfolio_nm"
                      value={formData.portfolio_nm}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                </TableRow>

                <TableRow>
                  <TableCell label="정렬순서" required>
                    <NumberBox
                      fieldName="sort_ordr"
                      value={formData.sort_ordr}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                  <TableCell label="사용여부" required>
                    <SelectBox
                      fieldName="use_at"
                      value={formData.use_at}
                      items={codeList?.useAt}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                    />
                  </TableCell>
                </TableRow>

                <TableRow>
                  <TableCell label="설명" colSpan={3}>
                    <TextArea
                      fieldName="description"
                      value={formData.description}
                      onValueChanged={handleFieldChange}
                      getFieldProps={getFieldProps}
                      maxLength={1000}
                      height={100}
                    />
                  </TableCell>
                </TableRow>
              </TableGroup>
            </div>
          </div>
        </TabContent>

        <TabContent tabId="holdings">
          <div className="h-full flex flex-col">
            <div className="flex-shrink-0 mb-2">
              <div className="flex gap-2 justify-end">
                {onCancel && !isNew && <Button text="취소" onClick={onCancel} stylingMode="outlined" type="normal" />}
              </div>
            </div>

            <div className="flex-1 min-h-0 flex flex-col">
              <TableGroup title="보유종목 목록" mode="flex">
                <TableRow>
                  <TableCell>
                    <PortfolioHoldingGrid
                      portfolioId={formData.portfolio_id!}
                      editable={true}
                      height="100%"
                      codeList={codeList}
                    />
                  </TableCell>
                </TableRow>
              </TableGroup>
            </div>
          </div>
        </TabContent>
      </TabPanel>
    </div>
  );
}
