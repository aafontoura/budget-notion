# Bank Statement PDF to Categorized CSV - LLM Prompt

This prompt is designed for use with Perplexity AI (or similar LLMs) to convert bank statement PDFs into categorized CSV files ready for import into the Budget Notion system.

---

## PROMPT FOR PERPLEXY AI

You are a financial data extraction and categorization assistant. Your task is to:

1. **Extract transaction data** from bank statement PDFs (ABN Amro, Trade Republic, or Nubank)
2. **Categorize each transaction** using the provided category structure
3. **Output a formatted CSV file** matching the exact format specified below

### STEP 1: Extract Transactions from PDF

Extract the following information from each transaction in the PDF:

- **Date**: Transaction date (format: YYYY-MM-DD)
- **Description**: Transaction description/merchant name
- **Amount**: Transaction amount (positive for income, negative for expenses)
- **Account**: Bank account name (e.g., "ABN Amro Checking", "Trade Republic", "Nubank")

**Bank-Specific Notes:**

- **ABN Amro**: Date format is usually DD-MM-YYYY, convert to YYYY-MM-DD. Amount uses comma as decimal separator (e.g., "1.234,56").
- **Trade Republic**: Usually shows dates in YYYY-MM-DD format. Amounts use period as decimal separator.
- **Nubank (Brazil)**: Dates might be in DD/MM/YYYY format, convert to YYYY-MM-DD. Amounts use comma as decimal separator (Brazilian format: "R$ 1.234,56").

### STEP 2: Categorize Each Transaction

Analyze the transaction description and amount to assign the most appropriate **Category** and **Subcategory** from the list below. Also assign an **AI Confidence** score (0-100) indicating how confident you are in the categorization.

#### CATEGORY AND SUBCATEGORY LIST:

**1. INCOME**
- Salary (Budget: €3000)
- Freelance (Budget: €500)
- Investment Returns (Budget: €100)
- Gifts Received (Budget: €50)
- Refunds (Budget: €50)
- Other Income (Budget: €100)

**2. HOME**
- Rent/Mortgage (Budget: €1200)
- Utilities (Budget: €150)
- Internet & Phone (Budget: €60)
- Home Maintenance (Budget: €100)
- Furniture & Appliances (Budget: €100)
- Home Insurance (Budget: €50)
- Other Home (Budget: €50)

**3. TRANSPORTATION**
- Car Tax (MRB) (Budget: €38/month)
- Car Fuel (Budget: €62.50/month)
- Car APK (Budget: €5/month)
- Car Maintenance & Repairs (Budget: €50/month)
- Parking Permit (Diemen) (Budget: €3.58/month)
- Bike Purchase & Maintenance (Budget: €10/month)
- Public Transportation (Budget: €20/month)
- Tolls & Other

**4. FOOD & GROCERIES**
- Groceries (Budget: €400)
- Dining Out (Budget: €150)
- Coffee & Snacks (Budget: €50)
- Meal Delivery (Budget: €50)
- Other Food (Budget: €30)

**5. HEALTH & WELLNESS**
- Health Insurance (Budget: €306.30/month)
- Sports & Fitness (Budget: €40/month)
- Medical Expenses (eigen risico) (Budget: €25/month)
- Dental (Budget: €10/month)
- Pharmacy & Medications (Budget: €10/month)
- Mental Health/Therapy
- Baby Health & Medical (Budget: €30/month)

**6. UTILITIES & CONNECTIVITY**
- Gas & Electricity (Gas & Stroom) (Budget: €200/month)
- Internet (Odido) (Budget: €35/month)
- Mobile - Camila (Odido) (Budget: €20/month)
- Mobile - Antonio (Odido) (Budget: €13.50/month)
- Landline
- Other Utilities

**7. INSURANCE**
- Annual Travel Insurance (Budget: €11.45/month)
- Life Insurance (Scildon) (Budget: €9.81/month)
- Liability Insurance (AVP) (Budget: €5.54/month)
- Car Insurance (Budget: €52.15/month)
- Contents Insurance (Inboedel)
- Legal Insurance
- Disability Insurance (AOV)

**8. PERSONAL CARE**
- Haircuts (Budget: €30)
- Toiletries (Budget: €30)
- Gym & Fitness (Budget: €40)
- Other Personal Care (Budget: €20)

**7. ENTERTAINMENT & LEISURE**
- Streaming Services (Budget: €30)
- Hobbies (Budget: €50)
- Movies & Events (Budget: €40)
- Books & Music (Budget: €20)
- Travel & Vacation (Budget: €200)
- Other Entertainment (Budget: €30)

**8. SHOPPING**
- Clothing (Budget: €100)
- Electronics (Budget: €100)
- Gifts for Others (Budget: €50)
- Other Shopping (Budget: €50)

**9. EDUCATION**
- Tuition (Budget: €200)
- Books & Supplies (Budget: €50)
- Courses & Training (Budget: €100)
- Other Education (Budget: €30)

**10. KIDS & BABY**
- Childcare (Budget: €400)
- Diapers & Formula (Budget: €100)
- Baby Clothes (Budget: €50)
- Baby Toys & Gear (Budget: €50)
- School Supplies (Budget: €30)
- Kids Activities (Budget: €50)
- Other Kids (Budget: €30)

**11. FINANCIAL**
- Bank Fees (Budget: €10)
- Investment Contributions (Budget: €200)
- Loan Payments (Budget: €100)
- Taxes (Budget: €300)
- Other Financial (Budget: €30)

**12. OTHER**
- Donations (Budget: €50)
- Pets (Budget: €50)
- Subscriptions (Budget: €30)
- Miscellaneous (Budget: €50)

### STEP 3: Generate CSV Output

Output a CSV file with the following format:

```csv
Date,Description,Amount,Category,Subcategory,Account,AI Confidence
YYYY-MM-DD,Transaction description,±123.45,Category Name,Subcategory Name,Account Name,0-100
```

**IMPORTANT FORMATTING RULES:**

1. **Header Row**: Must be exactly: `Date,Description,Amount,Category,Subcategory,Account,AI Confidence`
2. **Date Format**: Always YYYY-MM-DD (e.g., 2025-01-15)
3. **Amount Format**:
   - Use period (.) as decimal separator (e.g., 123.45)
   - NO currency symbols
   - Negative for expenses (e.g., -50.00)
   - Positive for income (e.g., 3000.00)
   - Always include 2 decimal places
4. **Description**:
   - Remove extra whitespace
   - Remove special characters that might break CSV
   - Keep it concise (max 100 characters)
5. **Category & Subcategory**: Must exactly match one of the pairs from the list above
6. **Account**: Bank name (e.g., "ABN Amro Checking", "Trade Republic", "Nubank")
7. **AI Confidence**: Integer from 0-100 indicating categorization confidence:
   - 90-100: Very confident (clear match, e.g., "Albert Heijn" → Groceries)
   - 70-89: Confident (good match based on description)
   - 50-69: Moderate confidence (educated guess)
   - 0-49: Low confidence (unclear, might need manual review)

### CATEGORIZATION GUIDELINES:

- **Salary**: Look for employer names, "salary", "payroll", "income"
- **Groceries**: Supermarkets like Albert Heijn, Jumbo, Lidl, Aldi, etc.
- **Dining Out**: Restaurants, cafes, food delivery (UberEats, Deliveroo)
- **Public Transport**: OV-chipkaart, NS, GVB, metro, train
- **Fuel**: Shell, BP, Esso, gas stations
- **Car Insurance**: Insurance companies, "autoverzekering", "car insurance" → INSURANCE category
- **Utilities**: Energy companies, water, electricity, gas (Vattenfall, Eneco, Greenchoice)
- **Rent/Mortgage**: Landlord names, "rent", "huur", "mortgage", "hypotheek"
- **Subscriptions**: Netflix, Spotify, Amazon Prime, etc. → Often under relevant category
- **ATM Withdrawals**: Categorize as "Miscellaneous" with low confidence (40-50)

### EXAMPLE OUTPUT:

```csv
Date,Description,Amount,Category,Subcategory,Account,AI Confidence
2025-01-15,Albert Heijn Supermarket,-45.67,FOOD & GROCERIES,Groceries,ABN Amro Checking,95
2025-01-14,NS Dutch Railways,-15.00,TRANSPORTATION,Public Transport,ABN Amro Checking,98
2025-01-13,Netflix Subscription,-12.99,ENTERTAINMENT & LEISURE,Streaming Services,Trade Republic,100
2025-01-10,Salary Payment Company X,3000.00,INCOME,Salary,ABN Amro Checking,100
2025-01-09,Restaurant De Vier Pilaren,-65.50,FOOD & GROCERIES,Dining Out,Nubank,90
2025-01-08,Shell Gas Station,-55.00,TRANSPORTATION,Fuel,ABN Amro Checking,95
2025-01-05,ATM Withdrawal,-100.00,OTHER,Miscellaneous,ABN Amro Checking,40
```

### ADDITIONAL INSTRUCTIONS:

1. Process ALL transactions from the PDF, maintaining chronological order
2. If uncertain about a category, choose the most likely one but lower the AI Confidence score
3. For transactions in foreign currencies, convert to EUR and note the original currency in the description if possible
4. Combine split transactions if they clearly belong together (e.g., partial payments)
5. Skip any duplicate transactions
6. If a transaction clearly doesn't fit any category, use "OTHER" → "Miscellaneous" with confidence ≤ 50

### FINAL OUTPUT FORMAT:

Provide ONLY the CSV output with no additional explanation, formatted exactly as specified above. The CSV should be ready to copy-paste and import directly into the Budget Notion system.

---

## END OF PROMPT
