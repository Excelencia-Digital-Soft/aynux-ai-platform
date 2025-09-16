#!/usr/bin/env python3
"""
Test script for JSON extraction utility
"""

import json
from app.utils import extract_json_from_text, extract_json_safely

# Test case 1: Text with <think> block and markdown code block (as provided by user)
test_text_1 = """<think>
Okay, so I need to analyze the user's message "Hola, ¿qué productos tienen disponibles?" which translates to "Hello, what products are available?" in English.

First, looking at the instructions provided, the task is to extract the user's intent and structure a JSON response with specific fields. The user has given an example of how to format this JSON, so I need to follow that structure closely.

The user message starts with a greeting "Hola," which is Spanish for "Hello." Then they ask about available products: "¿qué productos tienen disponibles?" This translates directly to asking what products are currently in stock or available. 

Now, looking at the INTENT ANALYSIS section provided, there are several intents listed:

1. show_general_catalog
2. search_specific_products
3. search_by_category
4. search_by_brand
5. search_by_price
6. get_product_details

The user's message doesn't mention any specific product, category, brand, or price range. They're simply asking for an overview of what products are available. So this falls under the first intent: "show_general_catalog."

Since there's no mention of specific terms, categories, brands, prices, or details about stock, featured products, sales, or actions needed beyond showing general info, those fields should be null.

So putting it all together, the JSON response would have:

- "intent" set to "show_general_catalog"
- No relevant search_terms since there's nothing specific mentioned
- "category" and "brand" as null
- All price-related fields (price_min, price_max) as null
- "specific_product" as null because no product name is given
- Flags for wants_stock_info, wants_featured, wants_sale as false because the user didn't ask about stock info or features/sales
- "action_needed" should be null since they're not initiating an action but asking a question

I need to make sure that search_terms only include meaningful words. In this case, there are no specific terms beyond "productos," which is just "products." But according to the instructions, I shouldn't include filler words, so maybe it's better to leave search_terms as null here.

Wait, but in the example provided by the user, they included "specific_product" as an exact product name or null. Since there isn't a specific product mentioned, that should be null too.

So the final JSON would reflect all these points without any filled fields except for intent.
</think>

```json
{
  "intent": "show_general_catalog",
  "search_terms": [],
  "category": null,
  "brand": null,
  "price_min": null,
  "price_max": null,
  "specific_product": null,
  "wants_stock_info": false,
  "wants_featured": false,
  "wants_sale": false,
  "action_needed": null
}
```"""

# Test case 2: Simple JSON without formatting
test_text_2 = '{"intent": "search_products", "category": "electronics"}'

# Test case 3: Plain text without JSON
test_text_3 = "This is just plain text without any JSON"

# Test case 4: JSON with extra text
test_text_4 = """
Here's my analysis:
```json
{
  "intent": "search_by_category",
  "category": "laptops",
  "brand": "Dell",
  "price_min": 500,
  "price_max": 1500
}
```
That's what I found.
"""

# Test case 5: Partial JSON in text
test_text_5 = """
The analysis shows:
"intent": "get_product_details",
"specific_product": "iPhone 15 Pro",
"wants_stock_info": true
But there might be more...
"""

def test_json_extraction():
    """Test the JSON extraction utility"""
    
    print("Testing JSON Extraction Utility\n")
    print("=" * 60)
    
    # Test 1: Complex text with thinking block
    print("\n1. Testing text with <think> block and markdown:")
    result1 = extract_json_from_text(test_text_1)
    if result1:
        print(f"✅ Successfully extracted JSON:")
        print(json.dumps(result1, indent=2))
    else:
        print("❌ Failed to extract JSON")
    
    # Test 2: Simple JSON
    print("\n2. Testing simple JSON:")
    result2 = extract_json_from_text(test_text_2)
    if result2:
        print(f"✅ Successfully extracted JSON:")
        print(json.dumps(result2, indent=2))
    else:
        print("❌ Failed to extract JSON")
    
    # Test 3: No JSON with default
    print("\n3. Testing plain text with default value:")
    default_value = {"intent": "fallback", "message": "No JSON found"}
    result3 = extract_json_from_text(test_text_3, default=default_value)
    if result3:
        print(f"✅ Returned default value:")
        print(json.dumps(result3, indent=2))
    else:
        print("❌ Failed to return default")
    
    # Test 4: JSON in markdown code block
    print("\n4. Testing JSON in markdown code block:")
    result4 = extract_json_from_text(test_text_4)
    if result4:
        print(f"✅ Successfully extracted JSON:")
        print(json.dumps(result4, indent=2))
    else:
        print("❌ Failed to extract JSON")
    
    # Test 5: Partial JSON extraction with required keys
    print("\n5. Testing partial JSON extraction with required keys:")
    result5 = extract_json_from_text(
        test_text_5, 
        required_keys=["intent", "specific_product"],
        default={"intent": "fallback"}
    )
    if result5:
        print(f"✅ Extracted partial JSON:")
        print(json.dumps(result5, indent=2))
    else:
        print("❌ Failed to extract partial JSON")
    
    # Test 6: Type-safe extraction
    print("\n6. Testing type-safe extraction (expecting dict):")
    result6 = extract_json_safely(
        '["item1", "item2"]',  # This is a list, not dict
        expected_type=dict,
        default={"intent": "default"}
    )
    if result6:
        print(f"✅ Returned default for wrong type:")
        print(json.dumps(result6, indent=2))
    else:
        print("❌ Failed type safety check")
    
    print("\n" + "=" * 60)
    print("Tests completed!")

if __name__ == "__main__":
    test_json_extraction()