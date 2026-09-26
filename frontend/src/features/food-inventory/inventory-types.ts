export type InventoryItem = {
  item_id: string;
  name: string;
  quantity: number;
  unit: string | null;
  low_stock_threshold: number | null;
};

export type GroceryItem = {
  grocery_item_id: string;
  name: string;
  quantity: number | null;
  unit: string | null;
  purchased: boolean;
  added_by: string | null;
};

export type AddInventoryInput = {
  name: string;
  quantity: number;
  unit?: string;
  low_stock_threshold?: number;
};

export type AddGroceryInput = {
  name: string;
  quantity?: number;
  unit?: string;
};
