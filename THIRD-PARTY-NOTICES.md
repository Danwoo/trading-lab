# 서드파티 라이선스 고지 (THIRD-PARTY-NOTICES)

프론트엔드(`frontend/`) 프로덕션 의존성 551개(전이 의존성 포함, devDependencies 제외) 를 대상으로 한다. §1·§2 가 그 551개고, §3 은 npm 을 거치지 않고 저장소에 직접 커밋된 번들 정적 자산(폰트 등)을 손으로 추가한 절이다.

**2026-08-06 갱신(#341 완주 — DevExtreme 제거 반영)** — 상용 6종과 그 전이 의존이 빠져 623→599개가 됐다. 사라진 24개: 상용 6종(`devextreme`·`devextreme-react`·`@devexpress/utils`·`devexpress-diagram`·`devexpress-gantt`·`@devextreme/runtime`)과 그것들만 쓰던 18개(`inferno` 계열 5 · `devextreme-quill`·`parchment`·`quill-delta`·`fast-diff`·`rrule`·`core-js`·`@babel/runtime`·`es6-object-assign`·`eventemitter3`·`lodash.clonedeep`·`lodash.isequal`·`lodash.merge`·`opencollective-postinstall`). 갱신은 손으로 지우지 않고 **아래 재현 명령의 새 출력을 정본으로 삼아 문서의 패키지 목록과 대조**했다 — 그 결과 「문서에 있는데 지금 없음」 24개 = 위 목록, 「지금 있는데 문서에 없음」 0개. 남은 599개에 DevExpress 계열은 `devextreme-exceljs-fork`(MIT 포크) 하나뿐이다.

**2026-08-04 갱신(#391 D3, O8-3/#341 이관 반영)** — radix-ui 이관 커널이 신규 프로덕션 패키지 73종(`@radix-ui/*` 60 + `radix-ui` 1 + `@floating-ui/*` 4 + `aria-hidden`·`detect-node-es`·`get-nonce`·`react-remove-scroll`·`react-remove-scroll-bar`·`react-style-singleton`·`use-callback-ref`·`use-sidecar` 8)을 들여와 550→623개로 늘었다. 아래 재현 명령의 실제 출력을 `main` 대비 `frontend/package-lock.json` diff(신규 76 항목 − 버전만 오른 기존 패키지 3 종 `axios`·`form-data`·`hasown` = 순증 73)와 대조해 신규분을 확정했다. **73종 전수를 `licenses-prod.json` 에서 개별 확인 — 전부 `MIT`, `licenseFile` 실재(파일 없음 0건).** 아래 §2 표에 반영했다.

생성 명령(재현 가능 — §1·§2 의 목록은 이 명령의 실제 출력에서 생성기가 만든다):

```bash
cd frontend && npm ci --ignore-scripts
npx --yes license-checker-rseidelsohn --production --excludePrivatePackages --json --out /tmp/licenses-prod.json
```

**§1·§2 의 개수·목록·라이선스 원문은 손으로 세지 않는다.** 의존성이 바뀌면
`python3 scripts/generate_notices.py` 를 돌려 다시 만들어 커밋한다. 어디까지가 생성기 소관이고
어디부터가 사람이 쓴 산문인지(라이선스 **분류** 판단·각 절의 설명·§3 전체)는 그 스크립트의 머리
주석이 경계로 적어 두었다 — 분류표에 없는 라이선스가 새로 들어오면 생성기는 그것을 §2
permissive 로 흘려보내지 않고 멈춘다(사람이 판단할 자리다).

**그리고 CI 가 매번 두 겹으로 대조한다 (#365, `test: frontend` 잡).**
`scripts/generate_notices.py --check` 는 「생성기 출력 = 커밋된 문서」를 보고,
`scripts/verify_notice_counts.py` 는 생성기 출력을 믿지 않고 **문서를 다시 파싱해** 「문서가
열거한 `이름@버전` 집합 = 실측 집합」을 양방향으로 본다(절 머리의 선언 개수·§3 의 폰트 파일
수까지 함께). 개수만 맞추면 「하나 빠지고 하나 더 들어온」 상태가 통과하므로 집합으로 본다 —
**숫자를 손으로 고치는 것으로는 초록이 되지 않는다.**

---

## ✅ 프로덕션 의존성에 상용 라이선스 없음

**DevExpress 상용(평가판) 6종이 전부 사라졌다** — `devextreme` · `devextreme-react` ·
`@devexpress/utils` · `devexpress-diagram` · `devexpress-gantt` · `@devextreme/runtime`.
#341 이 앱 코드·`package.json`·lockfile 어디에도 남지 않게 걷어냈고, 위 재현 명령의 산출물에도
이 6종은 없다(직접 대조 — 아래 검산 참고). 재도입은 CI 가 막는다
(`test: frontend-devextreme-scope` — 전이 import 그래프 순회 + 6종 주입 시험).

이제 프로덕션 의존성에 남은 비-permissive 라이선스는 아래 §1 의 것들뿐이고, 전부 재배포 조건이
고지·사본 동봉으로 충족되는 부류다(Apache-2.0 · MPL-2.0 · LGPL-3.0 · CC-BY-4.0 등).

`devextreme-exceljs-fork` 는 이름만 계열을 닮았을 뿐 **exceljs 의 MIT 포크**다(§2 표에 포함) —
`useExcelExport` · `useTableExport` 가 워크북 생성에 쓴다. 유일한 예외로 남긴 이유는
`.claude/docs/anti-patterns-frontend.md` 룰 4 참조.

---

## 1. 고지·확인이 필요한 라이선스

### Apache License 2.0

43개 패키지. Apache-2.0 은 재배포 시 라이선스 사본 동봉 + NOTICE 고지 승계 의무가 있다 — lightweight-charts 는 클라이언트 번들에 실려 브라우저로 나간다.

본문 텍스트 변형 14종(대체로 표준 Apache-2.0 원문, 일부 패키지가 자체 저작권 줄을 덧붙임)으로 묶는다.

<details><summary>변형 1 — 26개 패키지: `@opentelemetry/semantic-conventions@1.43.0`, `@prisma/adapter-pg@7.9.1`, `@prisma/client-runtime-utils@7.9.1`, `@prisma/client@7.9.1`, `@prisma/config@7.8.0`, `@prisma/debug@7.2.0`, `@prisma/debug@7.8.0`, `@prisma/debug@7.9.1`, `@prisma/driver-adapter-utils@7.9.1`, `@prisma/engines-version@7.8.0-6.3c6e192761c0362d496ed980de936e2f3cebcd3a`, `@prisma/engines@7.8.0`, `@prisma/fetch-engine@7.8.0`, `@prisma/get-platform@7.2.0`, `@prisma/get-platform@7.8.0`, `@prisma/query-plan-executor@7.2.0`, `b4a@1.8.1`, `bare-events@2.9.1`, `bare-fs@4.8.0`, `bare-path@3.1.1`, `bare-stream@2.13.3`, `bare-url@2.5.2`, `baseline-browser-mapping@2.11.14`, `events-universal@1.0.1`, `long@5.3.2`, `prisma@7.8.0`, `text-decoder@1.2.7`</summary>

```
Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```
</details>

<details><summary>변형 2 — 4개 패키지: `@electric-sql/pglite-socket@0.1.1`, `@electric-sql/pglite-tools@0.3.1`, `@electric-sql/pglite@0.4.1`, `xml-name-validator@5.0.0`</summary>

```
Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS
```
</details>

<details><summary>변형 3 — 2개 패키지: `@img/sharp-linux-x64@0.35.3`, `sharp@0.35.3`</summary>

```
Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

1. Definitions.

"License" shall mean the terms and conditions for use, reproduction, and
distribution as defined by Sections 1 through 9 of this document.

"Licensor" shall mean the copyright owner or entity authorized by the copyright
owner that is granting the License.

"Legal Entity" shall mean the union of the acting entity and all other entities
that control, are controlled by, or are under common control with that entity.
For the purposes of this definition, "control" means (i) the power, direct or
indirect, to cause the direction or management of such entity, whether by
contract or otherwise, or (ii) ownership of fifty percent (50%) or more of the
outstanding shares, or (iii) beneficial ownership of such entity.

"You" (or "Your") shall mean an individual or Legal Entity exercising
permissions granted by this License.

"Source" form shall mean the preferred form for making modifications, including
but not limited to software source code, documentation source, and configuration
files.

"Object" form shall mean any form resulting from mechanical transformation or
translation of a Source form, including but not limited to compiled object code,
generated documentation, and conversions to other media types.

"Work" shall mean the work of authorship, whether in Source or Object form, made
available under the License, as indicated by a copyright notice that is included
in or attached to the work (an example is provided in the Appendix below).

"Derivative Works" shall mean any work, whether in Source or Object form, that
is based on (or derived from) the Work and for which the editorial revisions,
annotations, elaborations, or other modifications represent, as a whole, an
original work of authorship. For the purposes of this License, Derivative Works
shall not include works that remain separable from, or merely link (or bind by
name) to the interfaces of, the Work and Derivative Works thereof.

"Contribution" shall mean any work of authorship, including the original version
of the Work and any modifications or additions to that Work or Derivative Works
thereof, that is intentionally submitted to Licensor for inclusion in the Work
by the copyright owner or by an individual or Legal Entity authorized to submit
on behalf of the copyright owner. For the purposes of this definition,
"submitted" means any form of electronic, verbal, or written communication sent
to the Licensor or its representatives, including but not limited to
communication on electronic mailing lists, source code control systems, and
issue tracking systems that are managed by, or on behalf of, the Licensor for
the purpose of discussing and improving the Work, but excluding communication
that is conspicuously marked or otherwise designated in writing by the copyright
owner as "Not a Contribution."

"Contributor" shall mean Licensor and any individual or Legal Entity on behalf
of whom a Contribution has been received by Licensor and subsequently
incorporated within the Work.

2. Grant of Copyright License.

Subject to the terms and conditions of this License, each Contributor hereby
grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free,
irrevocable copyright license to reproduce, prepare Derivative Works of,
publicly display, publicly perform, sublicense, and distribute the Work and such
Derivative Works in Source or Object form.

3. Grant of Patent License.

Subject to the terms and conditions of this License, each Contributor hereby
grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free,
irrevocable (except as stated in this section) patent license to make, have
made, use, offer to sell, sell, import, and otherwise transfer the Work, where
such license applies only to those patent claims licensable by such Contributor
that are necessarily infringed by their Contribution(s) alone or by combination
of their Contribution(s) with the Work to which such Contribution(s) was
submitted. If You institute patent litigation against any entity (including a
cross-claim or counterclaim in a lawsuit) alleging that the Work or a
Contribution incorporated within the Work constitutes direct or contributory
patent infringement, then any patent licenses granted to You under this License
for that Work shall terminate as of the date such litigation is filed.

4. Redistribution.

You may reproduce and distribute copies of the Work or Derivative Works thereof
in any medium, with or without modifications, and in Source or Object form,
provided that You meet the following conditions:

You must give any other recipients of the Work or Derivative Works a copy of
this License; and
You must cause any modified files to carry prominent notices stating that You
changed the files; and
You must retain, in the Source form of any Derivative Works that You distribute,
all copyright, patent, trademark, and attribution notices from the Source form
of the Work, excluding those notices that do not pertain to any part of the
Derivative Works; and
If the Work includes a "NOTICE" text file as part of its distribution, then any
Derivative Works that You distribute must include a readable copy of the
attribution notices contained within such NOTICE file, excluding those notices
that do not pertain to any part of the Derivative Works, in at least one of the
following places: within a NOTICE text file distributed as part of the
Derivative Works; within the Source form or documentation, if provided along
with the Derivative Works; or, within a display generated by the Derivative
Works, if and wherever such third-party notices normally appear. The contents of
the NOTICE file are for informational purposes only and do not modify the
License. You may add Your own attribution notices within Derivative Works that
You distribute, alongside or as an addendum to the NOTICE text from the Work,
provided that such additional attribution notices cannot be construed as
modifying the License.
You may add Your own copyright statement to Your modifications and may provide
additional or different license terms and conditions for use, reproduction, or
distribution of Your modifications, or for any such Derivative Works as a whole,
provided Your use, reproduction, and distribution of the Work otherwise complies
with the conditions stated in this License.

5. Submission of Contributions.

Unless You explicitly state otherwise, any Contribution intentionally submitted
for inclusion in the Work by You to the Licensor shall be under the terms and
conditions of this License, without any additional terms or conditions.
Notwithstanding the above, nothing herein shall supersede or modify the terms of
any separate license agreement you may have executed with Licensor regarding
such Contributions.

6. Trademarks.

This License does not grant permission to use the trade names, trademarks,
service marks, or product names of the Licensor, except as required for
reasonable and customary use in describing the origin of the Work and
reproducing the content of the NOTICE file.

7. Disclaimer of Warranty.

Unless required by applicable law or agreed to in writing, Licensor provides the
Work (and each Contributor provides its Contributions) on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied,
including, without limitation, any warranties or conditions of TITLE,
NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A PARTICULAR PURPOSE. You are
solely responsible for determining the appropriateness of using or
redistributing the Work and assume any risks associated with Your exercise of
permissions under this License.

8. Limitation of Liability.

In no event and under no legal theory, whether in tort (including negligence),
contract, or otherwise, unless required by applicable law (such as deliberate
and grossly negligent acts) or agreed to in writing, shall any Contributor be
liable to You for damages, including any direct, indirect, special, incidental,
or consequential damages of any character arising as a result of this License or
out of the use or inability to use the Work (including but not limited to
damages for loss of goodwill, work stoppage, computer failure or malfunction, or
any and all other commercial damages or losses), even if such Contributor has
been advised of the possibility of such damages.

9. Accepting Warranty or Additional Liability.

While redistributing the Work or Derivative Works thereof, You may choose to
offer, and charge a fee for, acceptance of support, warranty, indemnity, or
other liability obligations and/or rights consistent with this License. However,
in accepting such obligations, You may act only on Your own behalf and on Your
sole responsibility, not on behalf of any other Contributor, and only if You
agree to indemnify, defend, and hold each Contributor harmless for any liability
incurred by, or claims asserted against, such Contributor by reason of your
accepting any such warranty or additional liability.

END OF TERMS AND CONDITIONS

APPENDIX: How to apply the Apache License to your work

To apply the Apache License to your work, attach the following boilerplate
notice, with the fields enclosed by brackets "[]" replaced with your own
identifying information. (Don't include the brackets!) The text should be
enclosed in the appropriate comment syntax for the file format. We also
recommend that a file or class name and description of purpose be included on
the same "printed page" as the copyright notice for easier identification within
third-party archives.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```
</details>

<details><summary>변형 4 — 1개 패키지: `@prisma/streams-local@0.1.2`</summary>

```
Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf of
      any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```
</details>

<details><summary>변형 5 — 1개 패키지: `@prisma/studio-core@0.27.3`</summary>

```
Note: Use of this software in production is permitted under Apache 2.0.

Prisma branding (logos, attribution, etc.) must remain visible and unaltered.

See https://www.prisma.io/terms for details.
```
</details>

<details><summary>변형 6 — 1개 패키지: `@swc/helpers@0.5.23`</summary>

```
Apache License
                        Version 2.0, January 2004
                     http://www.apache.org/licenses/

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

1. Definitions.

   "License" shall mean the terms and conditions for use, reproduction,
   and distribution as defined by Sections 1 through 9 of this document.

   "Licensor" shall mean the copyright owner or entity authorized by
   the copyright owner that is granting the License.

   "Legal Entity" shall mean the union of the acting entity and all
   other entities that control, are controlled by, or are under common
   control with that entity. For the purposes of this definition,
   "control" means (i) the power, direct or indirect, to cause the
   direction or management of such entity, whether by contract or
   otherwise, or (ii) ownership of fifty percent (50%) or more of the
   outstanding shares, or (iii) beneficial ownership of such entity.

   "You" (or "Your") shall mean an individual or Legal Entity
   exercising permissions granted by this License.

   "Source" form shall mean the preferred form for making modifications,
   including but not limited to software source code, documentation
   source, and configuration files.

   "Object" form shall mean any form resulting from mechanical
   transformation or translation of a Source form, including but
   not limited to compiled object code, generated documentation,
   and conversions to other media types.

   "Work" shall mean the work of authorship, whether in Source or
   Object form, made available under the License, as indicated by a
   copyright notice that is included in or attached to the work
   (an example is provided in the Appendix below).

   "Derivative Works" shall mean any work, whether in Source or Object
   form, that is based on (or derived from) the Work and for which the
   editorial revisions, annotations, elaborations, or other modifications
   represent, as a whole, an original work of authorship. For the purposes
   of this License, Derivative Works shall not include works that remain
   separable from, or merely link (or bind by name) to the interfaces of,
   the Work and Derivative Works thereof.

   "Contribution" shall mean any work of authorship, including
   the original version of the Work and any modifications or additions
   to that Work or Derivative Works thereof, that is intentionally
   submitted to Licensor for inclusion in the Work by the copyright owner
   or by an individual or Legal Entity authorized to submit on behalf of
   the copyright owner. For the purposes of this definition, "submitted"
   means any form of electronic, verbal, or written communication sent
   to the Licensor or its representatives, including but not limited to
   communication on electronic mailing lists, source code control systems,
   and issue tracking systems that are managed by, or on behalf of, the
   Licensor for the purpose of discussing and improving the Work, but
   excluding communication that is conspicuously marked or otherwise
   designated in writing by the copyright owner as "Not a Contribution."

   "Contributor" shall mean Licensor and any individual or Legal Entity
   on behalf of whom a Contribution has been received by Licensor and
   subsequently incorporated within the Work.

2. Grant of Copyright License. Subject to the terms and conditions of
   this License, each Contributor hereby grants to You a perpetual,
   worldwide, non-exclusive, no-charge, royalty-free, irrevocable
   copyright license to reproduce, prepare Derivative Works of,
   publicly display, publicly perform, sublicense, and distribute the
   Work and such Derivative Works in Source or Object form.

3. Grant of Patent License. Subject to the terms and conditions of
   this License, each Contributor hereby grants to You a perpetual,
   worldwide, non-exclusive, no-charge, royalty-free, irrevocable
   (except as stated in this section) patent license to make, have made,
   use, offer to sell, sell, import, and otherwise transfer the Work,
   where such license applies only to those patent claims licensable
   by such Contributor that are necessarily infringed by their
   Contribution(s) alone or by combination of their Contribution(s)
   with the Work to which such Contribution(s) was submitted. If You
   institute patent litigation against any entity (including a
   cross-claim or counterclaim in a lawsuit) alleging that the Work
   or a Contribution incorporated within the Work constitutes direct
   or contributory patent infringement, then any patent licenses
   granted to You under this License for that Work shall terminate
   as of the date such litigation is filed.

4. Redistribution. You may reproduce and distribute copies of the
   Work or Derivative Works thereof in any medium, with or without
   modifications, and in Source or Object form, provided that You
   meet the following conditions:

   (a) You must give any other recipients of the Work or
       Derivative Works a copy of this License; and

   (b) You must cause any modified files to carry prominent notices
       stating that You changed the files; and

   (c) You must retain, in the Source form of any Derivative Works
       that You distribute, all copyright, patent, trademark, and
       attribution notices from the Source form of the Work,
       excluding those notices that do not pertain to any part of
       the Derivative Works; and

   (d) If the Work includes a "NOTICE" text file as part of its
       distribution, then any Derivative Works that You distribute must
       include a readable copy of the attribution notices contained
       within such NOTICE file, excluding those notices that do not
       pertain to any part of the Derivative Works, in at least one
       of the following places: within a NOTICE text file distributed
       as part of the Derivative Works; within the Source form or
       documentation, if provided along with the Derivative Works; or,
       within a display generated by the Derivative Works, if and
       wherever such third-party notices normally appear. The contents
       of the NOTICE file are for informational purposes only and
       do not modify the License. You may add Your own attribution
       notices within Derivative Works that You distribute, alongside
       or as an addendum to the NOTICE text from the Work, provided
       that such additional attribution notices cannot be construed
       as modifying the License.

   You may add Your own copyright statement to Your modifications and
   may provide additional or different license terms and conditions
   for use, reproduction, or distribution of Your modifications, or
   for any such Derivative Works as a whole, provided Your use,
   reproduction, and distribution of the Work otherwise complies with
   the conditions stated in this License.

5. Submission of Contributions. Unless You explicitly state otherwise,
   any Contribution intentionally submitted for inclusion in the Work
   by You to the Licensor shall be under the terms and conditions of
   this License, without any additional terms or conditions.
   Notwithstanding the above, nothing herein shall supersede or modify
   the terms of any separate license agreement you may have executed
   with Licensor regarding such Contributions.

6. Trademarks. This License does not grant permission to use the trade
   names, trademarks, service marks, or product names of the Licensor,
   except as required for reasonable and customary use in describing the
   origin of the Work and reproducing the content of the NOTICE file.

7. Disclaimer of Warranty. Unless required by applicable law or
   agreed to in writing, Licensor provides the Work (and each
   Contributor provides its Contributions) on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
   implied, including, without limitation, any warranties or conditions
   of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
   PARTICULAR PURPOSE. You are solely responsible for determining the
   appropriateness of using or redistributing the Work and assume any
   risks associated with Your exercise of permissions under this License.

8. Limitation of Liability. In no event and under no legal theory,
   whether in tort (including negligence), contract, or otherwise,
   unless required by applicable law (such as deliberate and grossly
   negligent acts) or agreed to in writing, shall any Contributor be
   liable to You for damages, including any direct, indirect, special,
   incidental, or consequential damages of any character arising as a
   result of this License or out of the use or inability to use the
   Work (including but not limited to damages for loss of goodwill,
   work stoppage, computer failure or malfunction, or any and all
   other commercial damages or losses), even if such Contributor
   has been advised of the possibility of such damages.

9. Accepting Warranty or Additional Liability. While redistributing
   the Work or Derivative Works thereof, You may choose to offer,
   and charge a fee for, acceptance of support, warranty, indemnity,
   or other liability obligations and/or rights consistent with this
   License. However, in accepting such obligations, You may act only
   on Your own behalf and on Your sole responsibility, not on behalf
   of any other Contributor, and only if You agree to indemnify,
   defend, and hold each Contributor harmless for any liability
   incurred by, or claims asserted against, such Contributor by reason
   of your accepting any such warranty or additional liability.

END OF TERMS AND CONDITIONS

APPENDIX: How to apply the Apache License to your work.

   To apply the Apache License to your work, attach the following
   boilerplate notice, with the fields enclosed by brackets "[]"
   replaced with your own identifying information. (Don't include
   the brackets!)  The text should be enclosed in the appropriate
   comment syntax for the file format. We also recommend that a
   file or class name and description of purpose be included on the
   same "printed page" as the copyright notice for easier
   identification within third-party archives.

Copyright 2024 SWC contributors.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

	http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```
</details>

<details><summary>변형 7 — 1개 패키지: `crc-32@1.2.2`</summary>

```
Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "{}"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright (C) 2014-present   SheetJS LLC

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```
</details>

<details><summary>변형 8 — 1개 패키지: `denque@2.1.0`</summary>

```
Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright 2018-present Invertase Limited

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```
</details>

<details><summary>변형 9 — 1개 패키지: `detect-libc@2.1.2`</summary>

```
Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "{}"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright {yyyy} {name of copyright owner}

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```
</details>

<details><summary>변형 10 — 1개 패키지: `ecdsa-sig-formatter@1.0.11`</summary>

```
Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "{}"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright 2015 D2L Corporation

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```
</details>

<details><summary>변형 11 — 1개 패키지: `expect-type@1.4.0`</summary>

```
Copyright 2024 Misha Kaletsky

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.


                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS
```
</details>

<details><summary>변형 12 — 1개 패키지: `lightweight-charts@5.2.1`</summary>

```
Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright 2023 TradingView, Inc.

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```
</details>

<details><summary>변형 13 — 1개 패키지: `readdir-glob@3.0.0`</summary>

```
Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright 2020 Yann Armelin

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```
</details>

<details><summary>변형 14 — 1개 패키지: `typescript@6.0.3`</summary>

```
Apache License

Version 2.0, January 2004

http://www.apache.org/licenses/ 

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

1. Definitions.

"License" shall mean the terms and conditions for use, reproduction, and distribution as defined by Sections 1 through 9 of this document.

"Licensor" shall mean the copyright owner or entity authorized by the copyright owner that is granting the License.

"Legal Entity" shall mean the union of the acting entity and all other entities that control, are controlled by, or are under common control with that entity. For the purposes of this definition, "control" means (i) the power, direct or indirect, to cause the direction or management of such entity, whether by contract or otherwise, or (ii) ownership of fifty percent (50%) or more of the outstanding shares, or (iii) beneficial ownership of such entity.

"You" (or "Your") shall mean an individual or Legal Entity exercising permissions granted by this License.

"Source" form shall mean the preferred form for making modifications, including but not limited to software source code, documentation source, and configuration files.

"Object" form shall mean any form resulting from mechanical transformation or translation of a Source form, including but not limited to compiled object code, generated documentation, and conversions to other media types.

"Work" shall mean the work of authorship, whether in Source or Object form, made available under the License, as indicated by a copyright notice that is included in or attached to the work (an example is provided in the Appendix below).

"Derivative Works" shall mean any work, whether in Source or Object form, that is based on (or derived from) the Work and for which the editorial revisions, annotations, elaborations, or other modifications represent, as a whole, an original work of authorship. For the purposes of this License, Derivative Works shall not include works that remain separable from, or merely link (or bind by name) to the interfaces of, the Work and Derivative Works thereof.

"Contribution" shall mean any work of authorship, including the original version of the Work and any modifications or additions to that Work or Derivative Works thereof, that is intentionally submitted to Licensor for inclusion in the Work by the copyright owner or by an individual or Legal Entity authorized to submit on behalf of the copyright owner. For the purposes of this definition, "submitted" means any form of electronic, verbal, or written communication sent to the Licensor or its representatives, including but not limited to communication on electronic mailing lists, source code control systems, and issue tracking systems that are managed by, or on behalf of, the Licensor for the purpose of discussing and improving the Work, but excluding communication that is conspicuously marked or otherwise designated in writing by the copyright owner as "Not a Contribution."

"Contributor" shall mean Licensor and any individual or Legal Entity on behalf of whom a Contribution has been received by Licensor and subsequently incorporated within the Work.

2. Grant of Copyright License. Subject to the terms and conditions of this License, each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable copyright license to reproduce, prepare Derivative Works of, publicly display, publicly perform, sublicense, and distribute the Work and such Derivative Works in Source or Object form.

3. Grant of Patent License. Subject to the terms and conditions of this License, each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable (except as stated in this section) patent license to make, have made, use, offer to sell, sell, import, and otherwise transfer the Work, where such license applies only to those patent claims licensable by such Contributor that are necessarily infringed by their Contribution(s) alone or by combination of their Contribution(s) with the Work to which such Contribution(s) was submitted. If You institute patent litigation against any entity (including a cross-claim or counterclaim in a lawsuit) alleging that the Work or a Contribution incorporated within the Work constitutes direct or contributory patent infringement, then any patent licenses granted to You under this License for that Work shall terminate as of the date such litigation is filed.

4. Redistribution. You may reproduce and distribute copies of the Work or Derivative Works thereof in any medium, with or without modifications, and in Source or Object form, provided that You meet the following conditions:

You must give any other recipients of the Work or Derivative Works a copy of this License; and

You must cause any modified files to carry prominent notices stating that You changed the files; and

You must retain, in the Source form of any Derivative Works that You distribute, all copyright, patent, trademark, and attribution notices from the Source form of the Work, excluding those notices that do not pertain to any part of the Derivative Works; and

If the Work includes a "NOTICE" text file as part of its distribution, then any Derivative Works that You distribute must include a readable copy of the attribution notices contained within such NOTICE file, excluding those notices that do not pertain to any part of the Derivative Works, in at least one of the following places: within a NOTICE text file distributed as part of the Derivative Works; within the Source form or documentation, if provided along with the Derivative Works; or, within a display generated by the Derivative Works, if and wherever such third-party notices normally appear. The contents of the NOTICE file are for informational purposes only and do not modify the License. You may add Your own attribution notices within Derivative Works that You distribute, alongside or as an addendum to the NOTICE text from the Work, provided that such additional attribution notices cannot be construed as modifying the License. You may add Your own copyright statement to Your modifications and may provide additional or different license terms and conditions for use, reproduction, or distribution of Your modifications, or for any such Derivative Works as a whole, provided Your use, reproduction, and distribution of the Work otherwise complies with the conditions stated in this License.

5. Submission of Contributions. Unless You explicitly state otherwise, any Contribution intentionally submitted for inclusion in the Work by You to the Licensor shall be under the terms and conditions of this License, without any additional terms or conditions. Notwithstanding the above, nothing herein shall supersede or modify the terms of any separate license agreement you may have executed with Licensor regarding such Contributions.

6. Trademarks. This License does not grant permission to use the trade names, trademarks, service marks, or product names of the Licensor, except as required for reasonable and customary use in describing the origin of the Work and reproducing the content of the NOTICE file.

7. Disclaimer of Warranty. Unless required by applicable law or agreed to in writing, Licensor provides the Work (and each Contributor provides its Contributions) on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied, including, without limitation, any warranties or conditions of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A PARTICULAR PURPOSE. You are solely responsible for determining the appropriateness of using or redistributing the Work and assume any risks associated with Your exercise of permissions under this License.

8. Limitation of Liability. In no event and under no legal theory, whether in tort (including negligence), contract, or otherwise, unless required by applicable law (such as deliberate and grossly negligent acts) or agreed to in writing, shall any Contributor be liable to You for damages, including any direct, indirect, special, incidental, or consequential damages of any character arising as a result of this License or out of the use or inability to use the Work (including but not limited to damages for loss of goodwill, work stoppage, computer failure or malfunction, or any and all other commercial damages or losses), even if such Contributor has been advised of the possibility of such damages.

9. Accepting Warranty or Additional Liability. While redistributing the Work or Derivative Works thereof, You may choose to offer, and charge a fee for, acceptance of support, warranty, indemnity, or other liability obligations and/or rights consistent with this License. However, in accepting such obligations, You may act only on Your own behalf and on Your sole responsibility, not on behalf of any other Contributor, and only if You agree to indemnify, defend, and hold each Contributor harmless for any liability incurred by, or claims asserted against, such Contributor by reason of your accepting any such warranty or additional liability.

END OF TERMS AND CONDITIONS
```
</details>

### Mozilla Public License 2.0

lightningcss(+플랫폼 네이티브 바이너리) — `better-auth → vitest → vite` 경로로 프로덕션 트리에 전이 포함되나(`npm ls --omit=dev` 확인), 우리 코드가 직접 호출하지 않는 vite 내부 CSS 처리 도구다. 파일 단위 카피레프트라 우리 코드 전체엔 영향 없음.

| 패키지 | 버전 |
|---|---|
| `lightningcss-linux-x64-gnu` | 1.33.0 |
| `lightningcss` | 1.33.0 |

### GNU Lesser General Public License 3.0

`@img/sharp-libvips-*` — Next.js Image Optimization(`sharp`)이 서버에서 실제로 호출하는 네이티브 바이너리. libvips 자체가 여러 C 라이브러리(BSD·MPL·MIT·Apache 혼합)를 동적 링크로 번들한다 — 세부 내역은 패키지 자체의 README(https://github.com/lovell/sharp-libvips)가 최신 정본이므로 재작성하지 않고 링크로 가리킨다.

| 패키지 | 버전 |
|---|---|
| `@img/sharp-libvips-linux-x64` | 1.3.2 |

### jszip — 듀얼 라이선스

MIT 조건으로 사용(추가 의무 없음). GPL 조건은 선택하지 않았다.

| 패키지 | 버전 |
|---|---|
| `jszip` | 3.10.1 |

### pako — MIT + Zlib 결합

둘 다 permissive, 추가 고지 의무 없음.

| 패키지 | 버전 |
|---|---|
| `pako` | 1.0.11 |

### caniuse-lite — 데이터(코드 아님), Creative Commons Attribution 4.0

브라우저 호환성 통계 데이터. CC-BY 는 출처 표시 의무 — "Data via caniuse-lite (caniuse.com)".

| 패키지 | 버전 |
|---|---|
| `caniuse-lite` | 1.0.30001809 |

### mdn-data — 퍼블릭 도메인 동등

추가 의무 없음.

| 패키지 | 버전 |
|---|---|
| `mdn-data` | 2.27.1 |

### postgres — 퍼블릭 도메인 동등

추가 의무 없음.

| 패키지 | 버전 |
|---|---|
| `postgres` | 3.4.7 |

---

## 2. 그 외 permissive 라이선스 (500개)

MIT·ISC·BSD-2/3-Clause·0BSD·MIT-0·BlueOak-1.0.0·MIT\* 등 — 저작권·허가 고지 보존 외 추가 의무가 없다. **전수 확인 결과(`licenseFile` 키 존재 + 해당 경로에 파일 실재, `os.path.isfile` 로 확인) 500개 중 497개는 npm 배포본에 자기 라이선스 파일을 직접 동봉하고, 3개는 `package.json` 의 `license` 필드 선언만 있고 원문 파일이 없다** — 이슈 #287 이 `clsx` 를 예로 들며 경고한 바로 그 부류다(현재 잠긴 `clsx@2.1.1` 자체는 `node_modules/clsx/license` 를 동봉해 예외가 아님을 개별 확인했다 — 부류는 실재하되 해당 개체는 다른 3개였다). 전문을 이 문서에 반복하지 않고 목록만 남긴다 — 개별 원문은 위 재현 명령의 산출물(`/tmp/licenses-prod.json`) 또는 각 패키지 저장소에서 확인 가능하다.

### 예외 — 원문 파일 없이 선언만 있는 패키지 (3개)

이 3개는 `node_modules/<pkg>/` 안에 LICENSE·COPYING 류 파일이 전혀 없다(디렉토리 전체 확인). 고지 원문이 필요하면 `package.json` 의 선언(SPDX 식별자)을 신뢰하거나 업스트림 저장소·npm 레지스트리 페이지에서 직접 확인해야 한다 — 이 저장소 안에서는 원문을 재구성할 근거가 없다.

| 패키지 | 버전 | `package.json` 선언 |
|---|---|---|
| `@prisma/dev` | 0.24.3 | ISC |
| `client-only` | 0.0.1 | MIT |
| `fancy-canvas` | 2.1.0 | MIT |

<details><summary>펼치기 — 나머지 497개: 패키지 · 버전 · 라이선스</summary>

| 패키지 | 버전 | 라이선스 |
|---|---|---|
| `@asamuzakjp/css-color` | 6.0.5 | MIT |
| `@asamuzakjp/dom-selector` | 8.3.0 | MIT |
| `@better-auth/core` | 1.6.30 | MIT |
| `@better-auth/drizzle-adapter` | 1.6.30 | MIT |
| `@better-auth/kysely-adapter` | 1.6.30 | MIT |
| `@better-auth/memory-adapter` | 1.6.30 | MIT |
| `@better-auth/mongo-adapter` | 1.6.30 | MIT |
| `@better-auth/prisma-adapter` | 1.6.30 | MIT |
| `@better-auth/telemetry` | 1.6.30 | MIT |
| `@better-auth/utils` | 0.4.2 | MIT |
| `@better-auth/utils` | 0.5.0 | MIT |
| `@better-fetch/fetch` | 1.3.1 | MIT |
| `@bramus/specificity` | 2.4.2 | MIT |
| `@csstools/color-helpers` | 6.1.0 | MIT-0 |
| `@csstools/css-calc` | 3.3.0 | MIT |
| `@csstools/css-color-parser` | 4.1.10 | MIT |
| `@csstools/css-parser-algorithms` | 4.0.0 | MIT |
| `@csstools/css-syntax-patches-for-csstree` | 1.1.7 | MIT-0 |
| `@csstools/css-tokenizer` | 4.0.0 | MIT |
| `@exodus/bytes` | 1.15.1 | MIT |
| `@fast-csv/format` | 5.0.5 | MIT |
| `@fast-csv/parse` | 5.0.5 | MIT |
| `@floating-ui/core` | 1.8.0 | MIT |
| `@floating-ui/dom` | 1.8.0 | MIT |
| `@floating-ui/react-dom` | 2.1.9 | MIT |
| `@floating-ui/utils` | 0.2.12 | MIT |
| `@hono/node-server` | 1.19.11 | MIT |
| `@img/colour` | 1.1.0 | MIT |
| `@jridgewell/sourcemap-codec` | 1.5.5 | MIT |
| `@kurkle/color` | 0.3.4 | MIT |
| `@next/env` | 16.3.2 | MIT |
| `@next/swc-linux-x64-gnu` | 16.3.2 | MIT |
| `@noble/ciphers` | 2.1.1 | MIT |
| `@noble/hashes` | 2.2.0 | MIT |
| `@oxc-project/types` | 0.146.0 | MIT |
| `@radix-ui/number` | 1.1.3 | MIT |
| `@radix-ui/primitive` | 1.1.3 | MIT |
| `@radix-ui/primitive` | 1.1.7 | MIT |
| `@radix-ui/react-accessible-icon` | 1.1.15 | MIT |
| `@radix-ui/react-accordion` | 1.2.20 | MIT |
| `@radix-ui/react-alert-dialog` | 1.1.23 | MIT |
| `@radix-ui/react-arrow` | 1.1.15 | MIT |
| `@radix-ui/react-aspect-ratio` | 1.1.15 | MIT |
| `@radix-ui/react-avatar` | 1.2.6 | MIT |
| `@radix-ui/react-checkbox` | 1.3.11 | MIT |
| `@radix-ui/react-collapsible` | 1.1.20 | MIT |
| `@radix-ui/react-collection` | 1.1.15 | MIT |
| `@radix-ui/react-compose-refs` | 1.1.2 | MIT |
| `@radix-ui/react-compose-refs` | 1.1.5 | MIT |
| `@radix-ui/react-context-menu` | 2.3.7 | MIT |
| `@radix-ui/react-context` | 1.2.2 | MIT |
| `@radix-ui/react-dialog` | 1.1.23 | MIT |
| `@radix-ui/react-direction` | 1.1.4 | MIT |
| `@radix-ui/react-dismissable-layer` | 1.1.19 | MIT |
| `@radix-ui/react-dropdown-menu` | 2.1.24 | MIT |
| `@radix-ui/react-focus-guards` | 1.1.6 | MIT |
| `@radix-ui/react-focus-scope` | 1.1.16 | MIT |
| `@radix-ui/react-form` | 0.1.16 | MIT |
| `@radix-ui/react-hover-card` | 1.1.23 | MIT |
| `@radix-ui/react-id` | 1.1.4 | MIT |
| `@radix-ui/react-label` | 2.1.15 | MIT |
| `@radix-ui/react-menu` | 2.1.24 | MIT |
| `@radix-ui/react-menubar` | 1.1.24 | MIT |
| `@radix-ui/react-navigation-menu` | 1.2.22 | MIT |
| `@radix-ui/react-one-time-password-field` | 0.1.16 | MIT |
| `@radix-ui/react-password-toggle-field` | 0.1.11 | MIT |
| `@radix-ui/react-popover` | 1.1.23 | MIT |
| `@radix-ui/react-popper` | 1.3.7 | MIT |
| `@radix-ui/react-portal` | 1.1.17 | MIT |
| `@radix-ui/react-presence` | 1.1.10 | MIT |
| `@radix-ui/react-primitive` | 2.1.10 | MIT |
| `@radix-ui/react-primitive` | 2.1.3 | MIT |
| `@radix-ui/react-progress` | 1.1.16 | MIT |
| `@radix-ui/react-radio-group` | 1.4.7 | MIT |
| `@radix-ui/react-roving-focus` | 1.1.19 | MIT |
| `@radix-ui/react-scroll-area` | 1.2.18 | MIT |
| `@radix-ui/react-select` | 2.3.7 | MIT |
| `@radix-ui/react-separator` | 1.1.15 | MIT |
| `@radix-ui/react-slider` | 1.4.7 | MIT |
| `@radix-ui/react-slot` | 1.2.3 | MIT |
| `@radix-ui/react-slot` | 1.3.3 | MIT |
| `@radix-ui/react-switch` | 1.3.7 | MIT |
| `@radix-ui/react-tabs` | 1.1.21 | MIT |
| `@radix-ui/react-toast` | 1.2.23 | MIT |
| `@radix-ui/react-toggle-group` | 1.1.19 | MIT |
| `@radix-ui/react-toggle` | 1.1.10 | MIT |
| `@radix-ui/react-toggle` | 1.1.18 | MIT |
| `@radix-ui/react-toolbar` | 1.1.19 | MIT |
| `@radix-ui/react-tooltip` | 1.2.16 | MIT |
| `@radix-ui/react-use-callback-ref` | 1.1.4 | MIT |
| `@radix-ui/react-use-controllable-state` | 1.2.2 | MIT |
| `@radix-ui/react-use-controllable-state` | 1.2.6 | MIT |
| `@radix-ui/react-use-effect-event` | 0.0.2 | MIT |
| `@radix-ui/react-use-effect-event` | 0.0.5 | MIT |
| `@radix-ui/react-use-escape-keydown` | 1.1.5 | MIT |
| `@radix-ui/react-use-is-hydrated` | 0.1.3 | MIT |
| `@radix-ui/react-use-layout-effect` | 1.1.1 | MIT |
| `@radix-ui/react-use-layout-effect` | 1.1.4 | MIT |
| `@radix-ui/react-use-previous` | 1.1.4 | MIT |
| `@radix-ui/react-use-rect` | 1.1.4 | MIT |
| `@radix-ui/react-use-size` | 1.1.4 | MIT |
| `@radix-ui/react-visually-hidden` | 1.2.11 | MIT |
| `@radix-ui/rect` | 1.1.3 | MIT |
| `@rolldown/binding-linux-x64-gnu` | 1.2.5 | MIT |
| `@rolldown/pluginutils` | 1.0.1 | MIT |
| `@standard-schema/spec` | 1.1.0 | MIT |
| `@t3-oss/env-core` | 0.13.11 | MIT |
| `@t3-oss/env-nextjs` | 0.13.11 | MIT |
| `@tanstack/react-table` | 8.21.3 | MIT |
| `@tanstack/react-virtual` | 3.14.10 | MIT |
| `@tanstack/table-core` | 8.21.3 | MIT |
| `@tanstack/virtual-core` | 3.17.8 | MIT |
| `@types/chai` | 5.2.3 | MIT |
| `@types/debug` | 4.1.13 | MIT |
| `@types/deep-eql` | 4.0.2 | MIT |
| `@types/estree-jsx` | 1.0.5 | MIT |
| `@types/estree` | 1.0.8 | MIT |
| `@types/hast` | 3.0.4 | MIT |
| `@types/katex` | 0.16.8 | MIT |
| `@types/mdast` | 4.0.4 | MIT |
| `@types/ms` | 2.1.0 | MIT |
| `@types/node` | 26.2.0 | MIT |
| `@types/pg` | 8.20.0 | MIT |
| `@types/react-dom` | 19.2.4 | MIT |
| `@types/react` | 19.2.18 | MIT |
| `@types/unist` | 2.0.11 | MIT |
| `@types/unist` | 3.0.3 | MIT |
| `@ungap/structured-clone` | 1.3.1 | ISC |
| `@vitest/expect` | 4.1.11 | MIT |
| `@vitest/mocker` | 4.1.11 | MIT |
| `@vitest/pretty-format` | 4.1.11 | MIT |
| `@vitest/runner` | 4.1.11 | MIT |
| `@vitest/snapshot` | 4.1.11 | MIT |
| `@vitest/spy` | 4.1.11 | MIT |
| `@vitest/utils` | 4.1.11 | MIT |
| `abort-controller` | 3.0.0 | MIT |
| `agent-base` | 6.0.2 | MIT |
| `ajv` | 8.20.0 | MIT |
| `archiver` | 8.0.0 | MIT |
| `aria-hidden` | 1.2.6 | MIT |
| `assertion-error` | 2.0.1 | MIT |
| `async` | 3.2.6 | MIT |
| `asynckit` | 0.4.0 | MIT |
| `aws-ssl-profiles` | 1.1.2 | MIT |
| `axios` | 1.19.0 | MIT |
| `bail` | 2.0.2 | MIT |
| `balanced-match` | 4.0.4 | MIT |
| `base64-js` | 1.5.1 | MIT |
| `better-auth` | 1.6.30 | MIT |
| `better-call` | 1.4.0 | MIT |
| `better-result` | 2.9.2 | MIT |
| `bidi-js` | 1.0.3 | MIT |
| `bluebird` | 3.7.2 | MIT |
| `brace-expansion` | 5.0.9 | MIT |
| `buffer-crc32` | 1.0.0 | MIT |
| `buffer-equal-constant-time` | 1.0.1 | BSD-3-Clause |
| `buffer` | 6.0.3 | MIT |
| `c12` | 3.3.4 | MIT |
| `call-bind-apply-helpers` | 1.0.2 | MIT |
| `ccount` | 2.0.1 | MIT |
| `chai` | 6.2.2 | MIT |
| `character-entities-html4` | 2.1.0 | MIT |
| `character-entities-legacy` | 3.0.0 | MIT |
| `character-entities` | 2.0.2 | MIT |
| `character-reference-invalid` | 2.0.1 | MIT |
| `chart.js` | 4.5.1 | MIT |
| `chokidar` | 5.0.0 | MIT |
| `combined-stream` | 1.0.8 | MIT |
| `comma-separated-tokens` | 2.0.3 | MIT |
| `commander` | 8.3.0 | MIT |
| `compress-commons` | 7.0.1 | MIT |
| `confbox` | 0.2.4 | MIT |
| `convert-source-map` | 2.0.0 | MIT |
| `core-util-is` | 1.0.3 | MIT |
| `crc32-stream` | 7.0.1 | MIT |
| `cross-spawn` | 7.0.6 | MIT |
| `css-tree` | 3.2.1 | MIT |
| `csstype` | 3.2.3 | MIT |
| `data-urls` | 7.0.0 | MIT |
| `date-fns` | 4.4.0 | MIT |
| `dayjs` | 1.11.20 | MIT |
| `debug` | 4.4.3 | MIT |
| `decimal.js` | 10.6.0 | MIT |
| `decode-named-character-reference` | 1.3.0 | MIT |
| `deepmerge-ts` | 7.1.5 | BSD-3-Clause |
| `defu` | 6.1.7 | MIT |
| `delayed-stream` | 1.0.0 | MIT |
| `dequal` | 2.0.3 | MIT |
| `destr` | 2.0.5 | MIT |
| `detect-node-es` | 1.1.0 | MIT |
| `devextreme-exceljs-fork` | 4.4.13 | MIT |
| `devlop` | 1.1.0 | MIT |
| `dotenv` | 17.4.2 | BSD-2-Clause |
| `dunder-proto` | 1.0.1 | MIT |
| `duplexer2` | 0.1.4 | BSD-3-Clause |
| `effect` | 3.20.0 | MIT |
| `empathic` | 2.0.0 | MIT |
| `entities` | 6.0.1 | BSD-2-Clause |
| `entities` | 8.0.0 | BSD-2-Clause |
| `env-paths` | 3.0.0 | MIT |
| `es-define-property` | 1.0.1 | MIT |
| `es-errors` | 1.3.0 | MIT |
| `es-module-lexer` | 2.3.1 | MIT |
| `es-object-atoms` | 1.1.1 | MIT |
| `es-set-tostringtag` | 2.1.0 | MIT |
| `escape-string-regexp` | 5.0.0 | MIT |
| `estree-util-is-identifier-name` | 3.0.0 | MIT |
| `estree-walker` | 3.0.3 | MIT |
| `event-target-shim` | 5.0.1 | MIT |
| `events` | 3.3.0 | MIT |
| `exsolve` | 1.0.8 | MIT |
| `extend` | 3.0.2 | MIT |
| `fast-check` | 3.23.2 | MIT |
| `fast-csv` | 5.0.5 | MIT |
| `fast-deep-equal` | 3.1.3 | MIT |
| `fast-fifo` | 1.3.2 | MIT |
| `fast-uri` | 3.1.5 | BSD-3-Clause |
| `fdir` | 6.5.0 | MIT |
| `file-saver` | 2.0.5 | MIT |
| `follow-redirects` | 1.16.0 | MIT |
| `foreground-child` | 3.3.1 | ISC |
| `form-data` | 4.0.6 | MIT |
| `fs-extra` | 11.3.1 | MIT |
| `function-bind` | 1.1.2 | MIT |
| `generate-function` | 2.3.1 | MIT |
| `get-intrinsic` | 1.3.0 | MIT |
| `get-nonce` | 1.0.1 | MIT |
| `get-port-please` | 3.2.0 | MIT |
| `get-proto` | 1.0.1 | MIT |
| `giget` | 3.2.0 | MIT |
| `gopd` | 1.2.0 | MIT |
| `graceful-fs` | 4.2.11 | ISC |
| `grammex` | 3.1.12 | MIT |
| `graphmatch` | 1.1.1 | MIT |
| `has-symbols` | 1.1.0 | MIT |
| `has-tostringtag` | 1.0.2 | MIT |
| `hasown` | 2.0.4 | MIT |
| `hast-util-from-dom` | 5.0.1 | ISC |
| `hast-util-from-html-isomorphic` | 2.0.0 | MIT |
| `hast-util-from-html` | 2.0.3 | MIT |
| `hast-util-from-parse5` | 8.0.3 | MIT |
| `hast-util-is-element` | 3.0.0 | MIT |
| `hast-util-parse-selector` | 4.0.0 | MIT |
| `hast-util-to-jsx-runtime` | 2.3.6 | MIT |
| `hast-util-to-text` | 4.0.2 | MIT |
| `hast-util-whitespace` | 3.0.0 | MIT |
| `hastscript` | 9.0.1 | MIT |
| `hono` | 4.13.1 | MIT |
| `html-encoding-sniffer` | 6.0.0 | MIT |
| `html-url-attributes` | 3.0.1 | MIT |
| `http-status-codes` | 2.3.0 | MIT |
| `https-proxy-agent` | 5.0.1 | MIT |
| `iconv-lite` | 0.7.2 | MIT |
| `ieee754` | 1.2.1 | BSD-3-Clause |
| `immediate` | 3.0.6 | MIT |
| `inherits` | 2.0.4 | ISC |
| `inline-style-parser` | 0.2.7 | MIT |
| `is-alphabetical` | 2.0.1 | MIT |
| `is-alphanumerical` | 2.0.1 | MIT |
| `is-decimal` | 2.0.1 | MIT |
| `is-hexadecimal` | 2.0.1 | MIT |
| `is-plain-obj` | 4.1.0 | MIT |
| `is-potential-custom-element-name` | 1.0.1 | MIT |
| `is-property` | 1.0.2 | MIT |
| `is-stream` | 4.0.1 | MIT |
| `isarray` | 1.0.0 | MIT |
| `isexe` | 2.0.0 | ISC |
| `jiti` | 2.7.0 | MIT |
| `jose` | 6.2.10 | MIT |
| `jsdom` | 30.0.1 | MIT |
| `json-schema-traverse` | 1.0.0 | MIT |
| `jsonfile` | 6.2.0 | MIT |
| `jsonwebtoken` | 9.0.3 | MIT |
| `jwa` | 2.0.1 | MIT |
| `jws` | 4.0.1 | MIT |
| `katex` | 0.16.47 | MIT |
| `katex` | 0.17.0 | MIT |
| `kysely` | 0.28.17 | MIT |
| `lazystream` | 1.0.1 | MIT |
| `lie` | 3.3.0 | MIT |
| `lodash.escaperegexp` | 4.1.2 | MIT |
| `lodash.groupby` | 4.6.0 | MIT |
| `lodash.includes` | 4.3.0 | MIT |
| `lodash.isboolean` | 3.0.3 | MIT |
| `lodash.isfunction` | 3.0.9 | MIT |
| `lodash.isinteger` | 4.0.4 | MIT |
| `lodash.isnil` | 4.0.0 | MIT |
| `lodash.isnumber` | 3.0.3 | MIT |
| `lodash.isplainobject` | 4.0.6 | MIT |
| `lodash.isstring` | 4.0.1 | MIT |
| `lodash.isundefined` | 3.0.1 | MIT |
| `lodash.once` | 4.1.1 | MIT |
| `lodash.uniq` | 4.5.0 | MIT |
| `longest-streak` | 3.1.0 | MIT |
| `lru-cache` | 11.5.2 | BlueOak-1.0.0 |
| `lru.min` | 1.1.4 | MIT |
| `magic-string` | 0.30.21 | MIT |
| `markdown-table` | 3.0.4 | MIT |
| `math-intrinsics` | 1.1.0 | MIT |
| `mdast-util-find-and-replace` | 3.0.2 | MIT |
| `mdast-util-from-markdown` | 2.0.3 | MIT |
| `mdast-util-gfm-autolink-literal` | 2.0.1 | MIT |
| `mdast-util-gfm-footnote` | 2.1.0 | MIT |
| `mdast-util-gfm-strikethrough` | 2.0.0 | MIT |
| `mdast-util-gfm-table` | 2.0.0 | MIT |
| `mdast-util-gfm-task-list-item` | 2.0.0 | MIT |
| `mdast-util-gfm` | 3.1.0 | MIT |
| `mdast-util-math` | 3.0.0 | MIT |
| `mdast-util-mdx-expression` | 2.0.1 | MIT |
| `mdast-util-mdx-jsx` | 3.2.0 | MIT |
| `mdast-util-mdxjs-esm` | 2.0.1 | MIT |
| `mdast-util-phrasing` | 4.1.0 | MIT |
| `mdast-util-to-hast` | 13.2.1 | MIT |
| `mdast-util-to-markdown` | 2.1.2 | MIT |
| `mdast-util-to-string` | 4.0.0 | MIT |
| `micromark-core-commonmark` | 2.0.3 | MIT |
| `micromark-extension-gfm-autolink-literal` | 2.1.0 | MIT |
| `micromark-extension-gfm-footnote` | 2.1.0 | MIT |
| `micromark-extension-gfm-strikethrough` | 2.1.0 | MIT |
| `micromark-extension-gfm-table` | 2.1.1 | MIT |
| `micromark-extension-gfm-tagfilter` | 2.0.0 | MIT |
| `micromark-extension-gfm-task-list-item` | 2.1.0 | MIT |
| `micromark-extension-gfm` | 3.0.0 | MIT |
| `micromark-extension-math` | 3.1.0 | MIT |
| `micromark-factory-destination` | 2.0.1 | MIT |
| `micromark-factory-label` | 2.0.1 | MIT |
| `micromark-factory-space` | 2.0.1 | MIT |
| `micromark-factory-title` | 2.0.1 | MIT |
| `micromark-factory-whitespace` | 2.0.1 | MIT |
| `micromark-util-character` | 2.1.1 | MIT |
| `micromark-util-chunked` | 2.0.1 | MIT |
| `micromark-util-classify-character` | 2.0.1 | MIT |
| `micromark-util-combine-extensions` | 2.0.1 | MIT |
| `micromark-util-decode-numeric-character-reference` | 2.0.2 | MIT |
| `micromark-util-decode-string` | 2.0.1 | MIT |
| `micromark-util-encode` | 2.0.1 | MIT |
| `micromark-util-html-tag-name` | 2.0.1 | MIT |
| `micromark-util-normalize-identifier` | 2.0.1 | MIT |
| `micromark-util-resolve-all` | 2.0.1 | MIT |
| `micromark-util-sanitize-uri` | 2.0.1 | MIT |
| `micromark-util-subtokenize` | 2.1.0 | MIT |
| `micromark-util-symbol` | 2.0.1 | MIT |
| `micromark-util-types` | 2.0.2 | MIT |
| `micromark` | 4.0.2 | MIT |
| `mime-db` | 1.52.0 | MIT |
| `mime-types` | 2.1.35 | MIT |
| `minimatch` | 10.2.5 | BlueOak-1.0.0 |
| `ms` | 2.1.3 | MIT |
| `mysql2` | 3.15.3 | MIT |
| `named-placeholders` | 1.1.6 | MIT |
| `nanoid` | 3.3.18 | MIT |
| `nanostores` | 1.5.2 | MIT |
| `next` | 16.3.2 | MIT |
| `node-int64` | 0.4.0 | MIT |
| `nodemailer` | 9.0.5 | MIT-0 |
| `normalize-path` | 3.0.0 | MIT |
| `obug` | 2.1.4 | MIT |
| `ohash` | 2.0.11 | MIT |
| `parse-entities` | 4.0.2 | MIT |
| `parse5` | 7.3.0 | MIT |
| `parse5` | 8.0.1 | MIT |
| `path-key` | 3.1.1 | MIT |
| `pathe` | 2.0.3 | MIT |
| `perfect-debounce` | 2.1.0 | MIT |
| `pg-cloudflare` | 1.4.0 | MIT |
| `pg-connection-string` | 2.14.0 | MIT |
| `pg-int8` | 1.0.1 | ISC |
| `pg-pool` | 3.14.0 | MIT |
| `pg-protocol` | 1.15.0 | MIT |
| `pg-types` | 2.2.0 | MIT |
| `pg` | 8.22.0 | MIT |
| `pgpass` | 1.0.5 | MIT |
| `picocolors` | 1.1.1 | ISC |
| `picomatch` | 4.0.4 | MIT |
| `picomatch` | 4.0.5 | MIT |
| `pkg-types` | 2.3.1 | MIT |
| `postcss` | 8.5.23 | MIT |
| `postcss` | 8.5.26 | MIT |
| `postgres-array` | 2.0.0 | MIT |
| `postgres-array` | 3.0.4 | MIT |
| `postgres-bytea` | 1.0.1 | MIT |
| `postgres-date` | 1.0.7 | MIT |
| `postgres-interval` | 1.2.0 | MIT |
| `process-nextick-args` | 2.0.1 | MIT |
| `process` | 0.11.10 | MIT |
| `proper-lockfile` | 4.1.2 | MIT |
| `property-information` | 7.1.0 | MIT |
| `proxy-from-env` | 2.1.0 | MIT |
| `punycode` | 2.3.1 | MIT |
| `pure-rand` | 6.1.0 | MIT |
| `radix-ui` | 1.6.7 | MIT |
| `rc9` | 3.0.1 | MIT |
| `react-dom` | 19.2.8 | MIT |
| `react-icons` | 5.7.0 | MIT |
| `react-markdown` | 10.1.0 | MIT |
| `react-remove-scroll-bar` | 2.3.8 | MIT |
| `react-remove-scroll` | 2.7.2 | MIT |
| `react-resizable-panels` | 4.12.3 | MIT |
| `react-style-singleton` | 2.2.3 | MIT |
| `react` | 19.2.8 | MIT |
| `readable-stream` | 2.3.8 | MIT |
| `readable-stream` | 3.6.2 | MIT |
| `readable-stream` | 4.7.0 | MIT |
| `readdirp` | 5.0.0 | MIT |
| `rehype-katex` | 7.0.1 | MIT |
| `remark-gfm` | 4.0.1 | MIT |
| `remark-math` | 6.0.0 | MIT |
| `remark-parse` | 11.0.0 | MIT |
| `remark-rehype` | 11.1.2 | MIT |
| `remark-stringify` | 11.0.0 | MIT |
| `remeda` | 2.33.4 | MIT |
| `require-from-string` | 2.0.2 | MIT |
| `retry` | 0.12.0 | MIT |
| `rolldown` | 1.2.5 | MIT |
| `rou3` | 0.9.2 | MIT |
| `safe-buffer` | 5.1.2 | MIT |
| `safe-buffer` | 5.2.1 | MIT |
| `safer-buffer` | 2.1.2 | MIT |
| `saxes` | 5.0.1 | ISC |
| `saxes` | 6.0.0 | ISC |
| `scheduler` | 0.27.0 | MIT |
| `semver` | 7.8.5 | ISC |
| `seq-queue` | 0.0.5 | MIT* |
| `set-cookie-parser` | 3.1.2 | MIT |
| `setimmediate` | 1.0.5 | MIT |
| `shebang-command` | 2.0.0 | MIT |
| `shebang-regex` | 3.0.0 | MIT |
| `siginfo` | 2.0.0 | ISC |
| `signal-exit` | 3.0.7 | ISC |
| `signal-exit` | 4.1.0 | ISC |
| `source-map-js` | 1.2.1 | BSD-3-Clause |
| `space-separated-tokens` | 2.0.2 | MIT |
| `split2` | 4.2.0 | ISC |
| `sqlstring` | 2.3.3 | MIT |
| `stackback` | 0.0.2 | MIT |
| `std-env` | 3.10.0 | MIT |
| `std-env` | 4.2.0 | MIT |
| `streamx` | 2.28.0 | MIT |
| `string_decoder` | 1.1.1 | MIT |
| `string_decoder` | 1.3.0 | MIT |
| `stringify-entities` | 4.0.4 | MIT |
| `style-to-js` | 1.1.21 | MIT |
| `style-to-object` | 1.0.14 | MIT |
| `styled-jsx` | 5.1.6 | MIT |
| `symbol-tree` | 3.2.4 | MIT |
| `tar-stream` | 3.2.0 | MIT |
| `teex` | 1.0.1 | MIT |
| `tinybench` | 2.9.0 | MIT |
| `tinyexec` | 1.2.4 | MIT |
| `tinyglobby` | 0.2.17 | MIT |
| `tinyrainbow` | 3.1.1 | MIT |
| `tldts-core` | 7.4.10 | MIT |
| `tldts` | 7.4.10 | MIT |
| `tmp` | 0.2.7 | MIT |
| `tough-cookie` | 6.0.2 | BSD-3-Clause |
| `tr46` | 6.0.0 | MIT |
| `trim-lines` | 3.0.1 | MIT |
| `trough` | 2.2.0 | MIT |
| `tslib` | 2.8.1 | 0BSD |
| `undici-types` | 8.3.0 | MIT |
| `undici` | 8.9.0 | MIT |
| `unified` | 11.0.5 | MIT |
| `unist-util-find-after` | 5.0.0 | MIT |
| `unist-util-is` | 6.0.1 | MIT |
| `unist-util-position` | 5.0.0 | MIT |
| `unist-util-remove-position` | 5.0.0 | MIT |
| `unist-util-stringify-position` | 4.0.0 | MIT |
| `unist-util-visit-parents` | 6.0.2 | MIT |
| `unist-util-visit` | 5.1.0 | MIT |
| `universalify` | 2.0.1 | MIT |
| `unzipper` | 0.12.5 | MIT |
| `use-callback-ref` | 1.3.3 | MIT |
| `use-sidecar` | 1.1.3 | MIT |
| `util-deprecate` | 1.0.2 | MIT |
| `uuid` | 14.0.2 | MIT |
| `valibot` | 1.2.0 | MIT |
| `vfile-location` | 5.0.3 | MIT |
| `vfile-message` | 4.0.3 | MIT |
| `vfile` | 6.0.3 | MIT |
| `vite` | 8.2.2 | MIT |
| `vitest` | 4.1.11 | MIT |
| `w3c-xmlserializer` | 5.0.0 | MIT |
| `web-namespaces` | 2.0.1 | MIT |
| `webidl-conversions` | 8.0.1 | BSD-2-Clause |
| `whatwg-mimetype` | 5.0.0 | MIT |
| `whatwg-url` | 16.0.1 | MIT |
| `whatwg-url` | 17.1.0 | MIT |
| `which` | 2.0.2 | ISC |
| `why-is-node-running` | 2.3.0 | MIT |
| `xmlchars` | 2.2.0 | MIT |
| `xtend` | 4.0.2 | MIT |
| `yaml` | 2.8.3 | ISC |
| `zeptomatch` | 2.1.0 | MIT |
| `zip-stream` | 7.0.5 | MIT |
| `zod` | 4.4.3 | MIT |
| `zustand` | 5.0.15 | MIT |
| `zwitch` | 2.0.4 | MIT |

</details>

---

## 3. 번들 정적 자산 — npm 의존성 아님

위 §1·§2 는 `license-checker-rseidelsohn` 이 훑은 `frontend/` 프로덕션 npm 의존성만을 대상으로 한다(문서 맨 위 참조). `frontend/public/` 에는 npm 을 거치지 않고 저장소에 직접 커밋된 정적 자산도 있다 — `package.json` 에 등록되지 않으므로 위 재현 명령의 스캔 범위 밖이다. 이 절은 그중 라이선스 고지가 필요하다고 확인된 것을 손으로 기록한다(생성 명령 없음, 아래 확인 방법을 직접 밝힌다).

### Pretendard 폰트 — SIL Open Font License, Version 1.1

`frontend/public/font/woff/`·`frontend/public/font/woff2/` 에 굵기 9종(Thin~Black) × 포맷 2종(woff/woff2), 총 18개 파일을 번들해 재배포한다. `frontend/styles/fonts.css` 의 `@font-face` 9개가 이 18개 파일을 전부 참조하고, `frontend/app/layout.tsx` 가 `<body className="font-Pretendard">` 로 적용한다.

**실물 확인**: 이름만으로 판단하지 않고 woff·woff2 양쪽의 OpenType `name` 테이블을 각각 직접 파싱했다. 두 포맷은 압축 방식이 달라(woff 는 테이블별 zlib, woff2 는 전체 스트림 brotli) 검증 스크립트도 둘로 나눴다 — 둘 다 Node 표준 라이브러리(`zlib.inflateSync`·`zlib.brotliDecompressSync`, Node 11+, 이 레포는 Node 24 로 돈다)만 쓰고 외부 의존성이 없다:

```
$ node frontend/scripts/verify-woff-name-table.js frontend/public/font/woff/*.woff
검사 대상: 9개 파일 / 전부 일치: 예
$ node frontend/scripts/verify-woff2-name-table.js frontend/public/font/woff2/*.woff2
검사 대상: 9개 파일 / 전부 일치: 예
```

woff 9개·woff2 9개 = 18개 전부가 아래 3문자열을 담고 있고, 버전도 `Version 1.309` 로 두 포맷이 같다. woff2 는 brotli 압축이라 항상 woff 보다 작다(예: Thin 1,073,072→694,804바이트, Regular 1,115,060→765,892바이트, Black 1,139,968→800,404바이트) — **크기가 형제 파일과 일치한다는 근거는 쓰지 않는다**(사실이 아니다). 판단 근거는 `name` 테이블에 직접 담긴 문자열·버전 내용이다.

```
Copyright © 2023 Kil Hyung-jin
License: This Font Software is licensed under the SIL Open Font License, Version 1.1.
License URL: http://scripts.sil.org/OFL
```

**라이선스 원문**: https://raw.githubusercontent.com/orioncactus/pretendard/main/LICENSE (2026-08-03 확인) 을 그대로 받아 `frontend/public/font/OFL.txt` 에 두었다. 이 문서(`THIRD-PARTY-NOTICES.md`)가 아니라 폰트 파일과 같은 자리를 택한 이유 — OFL 조건 2 *"each copy contains the above copyright notice and this license"* 는 **실제 재배포되는 사본**을 대상으로 하는데, `frontend/public/` 은 그대로 정적 자산으로 빌드에 실려 나가는 반면 레포 루트 문서는 그렇다는 보장이 없다(`next.config.*`·`package.json` 어디에도 이 문서를 빌드 산출물에 복사하는 설정이 없음을 확인했다).

**저작권 고지 — 4줄, 1인이 아님**: 원문을 확인한 결과 Pretendard 는 다른 오픈소스 폰트를 조합한 결과물이라 저작권 줄이 4개다. 리드가 전달한 것은 첫 줄만이었다 — 다른 결론이 나오면 보고하라는 지시에 따라 적는다:

```
Copyright (c) 2021, Kil Hyung-jin (https://github.com/orioncactus/pretendard),
with Reserved Font Name 'Pretendard'.

Copyright 2014-2021 Adobe (http://www.adobe.com/),
with Reserved Font Name 'Source'.
Source is a trademark of Adobe in the United States and/or other countries.

Copyright (c) 2016 The Inter Project Authors (https://github.com/rsms/inter),
with Reserved Font Name 'Inter'.

Copyright 2021 The M+ FONTS Project Authors (https://github.com/coz-m/MPLUS_FONTS),
with Reserved Font Name 'M PLUS 1'.
```

전문은 `frontend/public/font/OFL.txt` 참조.

| 대상 | 파일 수 | 라이선스 |
|---|---|---|
| Pretendard (`.woff`, 9 굵기) | 9 | SIL OFL 1.1 |
| Pretendard (`.woff2`, 9 굵기) | 9 | SIL OFL 1.1 |

### shadcn/ui — `primitives/dialog.tsx` 소스 벤더링, MIT License

`frontend/components/shared/ui/primitives/dialog.tsx`(오버레이 프리미티브 커널, O8-3/#341)는 [shadcn/ui](https://ui.shadcn.com)의 Dialog 컴포넌트 소스를 시작점으로 이 레포 Tailwind 관례(border-gray-200/300·`rounded`, 별도 디자인 토큰 없음)에 맞춰 다시 쓴 것이다. `.docs/4-아키텍처/터미널-프론트엔드-구조.md` §2.7 이 이를 "의존성이 아니라 소스 출처"로 명시한다 — `npx shadcn` CLI 로 컴포넌트 소스 파일을 그대로 복사해 오는 배포 방식이라 `package.json` 에 등록되지 않고, npm 패키지가 아니므로 §1·§2 의 `license-checker` 스캔 범위 밖이다(§3 도입부와 같은 이유로 이 절에 손으로 기록한다). `primitives/*` 아래 앞으로 늘어날 다른 파일(§2.7 이 예고한 `popover.tsx` 등)도 같은 출처·같은 처리를 따른다.

shadcn/ui 저장소(https://github.com/shadcn-ui/ui)는 최상위 `LICENSE.md` 를 MIT 로 공표한다:

```
MIT License

Copyright (c) 2023 shadcn

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**검증 경계** — 이 작업 환경은 네트워크 접근이 없다(프론트엔드 워커 도구 프로필에 WebFetch 미보유 — 오더가 정보원, roles/README 「도구 프로필」). Pretendard 절처럼 파일에 실린 메타데이터를 직접 파싱해 대조하는 방법이 이 벤더링에는 적용되지 않는다(복사해 온 것은 바이너리 자산이 아니라 TypeScript 소스이고, 라이선스 원문 자체가 이 저장소 안 어디에도 실려 있지 않다). 위 라이선스 원문은 shadcn/ui 가 MIT 를 표방한다는 사실 자체는 이 레포의 여러 설계 문서·PR 코멘트가 이미 전제로 삼고 있으나(CONTEXT.md 결정 로그 2026-07-28, `.docs/4-아키텍처/터미널-프론트엔드-구조.md` §2.7), 이 문서에 옮긴 원문 바이트 단위 일치는 리뷰 시점에 위 저장소 링크에서 직접 재대조하기를 권한다 — 이 점을 명시하지 않고 "확인됨"으로 적으면 실행 없이 검증을 주장하는 것이 된다.

### 그 외 `frontend/public/` 번들 자산 — 작업 트리 기준 처리 완료

이 표는 **작업 트리(현재 체크아웃되는 파일)** 를 대상으로 한다. git 히스토리에 남아 있던 사본은
아래 「히스토리 노출면」에서 따로 다룬다.

같은 조사에서 함께 확인한 npm 미경유 자산 4개는 출처 메타데이터(PNG 텍스트 청크·EXIF)가 비어 있어
제3자 자산인지 자체 제작물인지 저장소 안에서는 판단할 근거가 없었다. MIT 공개 배포(#287)를
앞두고 재배포 가능 여부를 확인할 수 없어, 확인 대신 교체했다.

| 파일 | 이전 상태 | 처리 | 방식 |
|---|---|---|---|
| `bg1.png`(2,242,946바이트)·`bg2.png`(868,015바이트) | 로그인·회원가입류 화면 배경(`Login.tsx`·`Signup.tsx` 등 8곳) | 삭제 | CSS 그라디언트+격자로 대체. `frontend/styles/globals.css` `.auth-backdrop`/`.auth-backdrop--hero` 가 터미널 패널 시스템 토큰(`--slate-void`·`--slate-panel`·`--slate-line`·`--signal-warn`)을 재사용 — 새 팔레트 없음 |
| `logo-svg.png`(580바이트, 파일명과 달리 실제 포맷은 PNG 160×48 — `file` 로 확인) | 이메일 발신 첨부 로고(`auth.ts`·`email/route.ts`) | `logo.png`(14,368바이트, PNG 883×272)로 교체 | 배지 글리프 + "ACME" 워드마크 SVG를 코드로 작성해 sharp 로 래스터화. 색상은 인증 화면이 이미 쓰던 브랜드색(버튼 그라디언트 `#2E3BD0`~`#2C64F8`, 헤딩 `#303F67`) 재사용 |
| `favicon.ico`(162바이트) | 파비콘(`layout.tsx`) | 690바이트로 교체 | 같은 배지 글리프를 32×32 로 래스터화, 원본과 동일한 ICO 컨테이너 사양(단일 32×32 RGBA PNG-in-ICO) 유지 |

이미지·폰트 등 외부 자산은 새로 받아오지 않았다 — 전부 이 저장소의 기존 코드(색상·토큰)를 재료로
생성했다.

**실물 확인**: 위 바이트 수·포맷은 `ls -la frontend/public/`·`stat -c '%s'`·`file` 을 교체 전후
파일에 직접 실행해 확인했다(2026-08-03). `git grep -n "bg1\.png\|bg2\.png\|logo-svg\.png" --
frontend/` 로 옛 파일명 참조가 남지 않았음을 확인했다.

**생성 원본과 명령 (2026-08-07, #361)**: 위 「코드로 작성해 래스터화」는 한동안 **재현할 수
없는 주장**이었다 — 생성 SVG 도 래스터화 명령도 커밋되지 않았다. 지금은 소스
`frontend/scripts/brand/logo.svg`·`favicon.svg` 와 생성 명령
`node frontend/scripts/generate-brand-assets.js` 가 함께 커밋돼 있고, 같은 명령의 `--check`
모드가 CI(`ci.yml` 의 `test: frontend`)에서 매 PR 마다 **소스 → 산출물 바이트 재현**을 대조한다.
표의 `logo.png` 바이트 수가 15,106 → 14,368 로 바뀐 것은 이 재현 가능한 소스에서 다시 만든
결과다(아래 워드마크 절 참조).

### "ACME" 워드마크 글리프 — DejaVu Sans Bold 아웃라인, Bitstream Vera License

#361 이 「확인 안 되는 것」으로 남긴 축 — 워드마크가 **손으로 그린 path 인지 폰트 래스터인지** —
의 답은 **폰트 래스터였다**. 근거는 추정이 아니라 대조다: `sans-serif` + `font-weight:700` +
`font-size:168` 로 "ACME"를 렌더하면 네 글자의 잉크 폭이 커밋돼 있던 `logo.png` 와 **정확히
같다**(A 130 · C 105 · M 137 · E 88 px). 이 머신에서 fontconfig 가 그 조합에 물리는 얼굴이
**DejaVu Sans Bold 2.37** 이다.

**그래서 `<text>` 를 버리고 아웃라인 path 로 바꿨다.** `<text>` 로 두면 같은 SVG 가 렌더 머신의
폰트 설치 상태·freetype 버전에 따라 다른 PNG 를 낸다 — 재현 가능한 소스라는 이 절의 주장이
성립하지 않는다. `frontend/scripts/brand/logo.svg` 에는 그 네 글자의 윤곽선이 **좌표로**
박혀 있고, 폰트를 전혀 찾지 않는다.

그 좌표는 DejaVu Sans Bold 의 글리프 윤곽에서 나왔으므로 출처를 여기 적는다. DejaVu 는
Bitstream Vera License(+ Arev 확장, DejaVu 자체 변경분은 퍼블릭 도메인)로 **수정·재배포를
허용**한다. 폰트 파일 자체는 이 저장소에 싣지 않는다 — 배포되는 것은 렌더된 좌표뿐이다.

```
Fonts are (c) Bitstream (see below). DejaVu changes are in public domain.
Glyphs imported from Arev fonts are (c) Tavmjung Bah (see below)

Copyright (c) 2003 by Bitstream, Inc. All Rights Reserved. Bitstream Vera is
a trademark of Bitstream, Inc.

Copyright (c) 2006 by Tavmjong Bah. All Rights Reserved.
```

라이선스 전문: https://dejavu-fonts.github.io/License.html (폰트 `name` 테이블 ID 14 가 가리키는
주소). **검증 경계** — 위 저작권 문구는 이 머신에 설치된
`/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf` 의 `name` 테이블(ID 0·13)을 직접 파싱해
옮긴 것이고, 라이선스 **전문**은 네트워크 없이 확인할 수 없어 옮기지 않았다(Pretendard 절과
달리 원문 파일이 저장소 안에 없다).

### 히스토리 노출면 — 옛 개발 레포 히스토리에 남아 있는 자산 (2026-08-04 결정, #360)

> **이 저장소에는 아래 4개 blob 이 없다.** 이사(2026-08-07)로 이 공개 레포는 옛 개발 레포의
> 히스토리를 한 커밋도 싣지 않은 채 시작했다 — `git log --all -- frontend/public/bg1.png` 이
> 이 저장소에서 0건이다. 이 절은 **왜 그렇게 시작했는지와 무엇이 다시 들어오면 안 되는지**의
> 기록이며, 아래 명령·출력은 **옛 개발 레포에서** 잰 것이다.

**위 표의 「처리 완료」는 작업 트리 기준이다** — 현재 체크아웃되는 파일에 제3자 자산이 없다는
뜻이지, 저장소를 통째로 넘겨도 안전하다는 뜻이 아니다. 파일을 작업 트리에서 지워도
**git 히스토리에는 사본이 남고**, 아래 4개 blob 은 옛 개발 저장소 히스토리에 살아 있었다:

```
$ git log --all --oneline -- frontend/public/bg1.png
4a2057f fix(frontend): 출처 불명 번들 이미지 4개 교체 — 배경은 CSS 로, 로고·파비콘은 자체 생성 (#287) (#359)
30be362 fix(frontend): 출처 불명 번들 이미지 교체 — CSS 배경 + 코드 생성 로고/파비콘
fe23ee6 init: Fintech AI Platform — AI 투자 리서치 멀티에이전트 + 금융 MCP 스위트
$ git cat-file -s 659c2a410c20e4ab88795c690bb8fd2cbe607e42
2242946
```

**리드 결정(2026-08-04, #360)은 히스토리 재작성이 아니라 「히스토리 없이 배포」다.**
`git filter-repo` 로 blob 을 지우고 force push 하는 안은 **기각됐다** — 전 커밋 해시가 바뀌어
열린 PR·클론·이슈의 커밋 참조가 전부 깨지고, 아래 「남는 노출면」대로 GitHub 의 `refs/pull/*`
는 그렇게 해도 닫히지 않는다.

대신 **이 공개본은 옛 개발 레포의 히스토리를 한 커밋도 싣지 않았다.** 내보내기는
`scripts/release_public.py` 의 `git archive <커밋>` 한 갈래뿐이었고(그 명령은 트리만 tar 로 뱉는다),
내보낸 트리는 `scripts/verify_public_release_tree.py` 가 **아래 4개 blob 의 재유입을 해시로
차단**한 뒤에야 나갔다. 즉 옛 개발 저장소는 **보관용으로 비공개로 남았고**, 이 공개 레포는
히스토리 없는 스냅샷에서 시작했다 — 그 뒤의 개발은 여기서 이어지며(리드 결정 2026-08-07), 같은
게이트가 **매 PR 마다** 이 4개 blob 의 재유입을 계속 막는다.

아래 표는 그래서 **「제거했다」가 아니라 「공개본에 실리면 안 되는 것」의 목록**이다 —
`verify_public_release_tree.py` 의 `DENYLIST_BLOBS` 와 같은 4건이다.

| 경로 | blob | 크기 | 차단 판정 근거 |
|---|---|---|---|
| `frontend/public/bg1.png` | `659c2a41` | 2,242,946 | 이미지를 디코드하면 Adobe Illustrator 앱 아이콘("Ai" 라운드 사각 배지)이 그림 안에 렌더돼 있다 — 제3자 자산 |
| `frontend/public/bg2.png` | `74dd0535` | 868,015 | 같은 그림의 저알파 판본 |
| `frontend/public/logo-svg.png` | `ba0c0aee` | 580 | 출처 메타데이터가 없어 검증 불가. 작업 트리에서는 이미 교체돼 참조 0건 |
| `frontend/public/favicon.ico` | `2fe222a7` | 162 | 위와 동일. 690바이트 교체본(`2197be23`)은 그대로 유지된다 |

**판정 범위**(2026-08-05 전수 조사): 브랜치·태그에서 도달 가능한 전 blob 2,345개를 읽어
바이너리 24개를 가려낸 뒤 각각을 판정했다. 차단 4개, 유지 20개(Pretendard 18개 + 현재 쓰이는
`logo.png`·`favicon.ico`).
Pretendard 는 상류 `orioncactus/pretendard` v1.3.9 배포본과 **바이트 동일**(`Pretendard-Regular.woff`
의 blob SHA-1 이 상류 배포 파일과 같은 `e3b3a358…`)함을 확인했다 — 포맷 변환조차 하지 않았으므로
OFL 의 *Modified Version* 이 아니고, Reserved Font Name 조항에 걸리지 않는다. 그래서 유지한다.

현재 쓰이는 `logo.png`·`favicon.ico` 는 **공개본에 실린다** — `frontend/lib/auth/auth.ts` 와
`frontend/app/api/common/email/route.ts` 가 메일 첨부로 읽고 `frontend/app/layout.tsx` 가
파비콘으로 참조한다. 빠지면 화면·메일이 깨진다. 그래서 차단은 경로가 아니라 **blob ID 로**
건다 — `frontend/public/favicon.ico` 경로에는 차단 대상(162바이트, `2fe222a7`)과 실려야 할
현행본(690바이트, `2197be23`)이 히스토리에 함께 살아 있어, 경로 단위로 막으면 실려야 할 것까지
막힌다.

**히스토리 재작성이 기각된 또 하나의 이유 — GitHub 의 PR ref**: `refs/pull/*` 는 GitHub 이 서버
측에서 관리해 force push 로 지워지지 않는다. 이 저장소에는 PR ref 180개가 있고 그중 166개가
차단 대상 blob 을 트리에 담고 있으며, 브랜치·태그 어디에서도 도달되지 않는 커밋 116개(차단 대상
보유 61개)가 그쪽에만 남아 있다(2026-08-05 실측). 즉 **히스토리 재작성을 했더라도 GitHub 상의
노출면은 닫히지 않았을 것이다** — 그쪽을 닫으려면 GitHub Support 에 캐시·PR ref 정리를
요청하거나 저장소를 재생성해야 한다. 「히스토리 없이 새 레포로」가 그 요구를 애초에 만들지
않는다.
